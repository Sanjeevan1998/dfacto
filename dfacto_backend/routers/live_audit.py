"""
WebSocket router — Live Audit pipeline (on-device GenAI STT via ML Kit EventChannel).

Route: WS /ws/live-audit

Protocol
--------
Flutter → Backend  : text  {"type":"transcript_text","text":"...","isFinal":bool}
Flutter → Backend  : text  {"type":"stop"}
Backend → Flutter  : text  {"type":"result",...}   FactCheckResult
Backend → Flutter  : text  {"type":"done"}         after stop + all tasks finish
Backend → Flutter  : text  {"type":"error","message":"..."}

Architecture (3-layer pipeline)
--------------------------------

Layer 1 — Agent 1a: WebSocket ingestor
    Receives JSON text frames from Flutter.
    Pushes (text, is_final) tuples into the Agent 1b queue.
    Stops on {"type":"stop"} or WS disconnect.
    NOTE: isFinal=False partials are passed through so the buffer can ignore them.

Layer 2 — Agent 1b: Topic-Aware TranscriptBuffer + Segmenter
    pump_transcript() reads from the queue.
    Accumulates ONLY isFinal=True text into TranscriptBuffer (200-word trigger).
    When the buffer hits 200 words (or flush on stop):
      → Calls agents.topic_segmenter.segment_topics() [Gemini 2.0 Flash]
      → Routes TopicBlocks:
          COMPLETED → _fact_check_and_send()  (downstream to Agent 1c)
          ONGOING   → TranscriptBuffer.prepend_ongoing()  (carry into next cycle)
    Session history (all isFinal words) is maintained separately for context.

Layer 3 — Agent 1c → LangGraph pipeline
    classify_claim (Agent 0) → run_pipeline_from_claim → result to Flutter.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from agents.claim_classifier import extract_all_claims
from agents.supervisor import run_pipeline_from_claim
from agents.topic_segmenter import segment_topics

logger = logging.getLogger("dfacto.live_audit")

router = APIRouter()

# Trigger a topic-segmentation cycle after this many new isFinal words in the buffer.
BUFFER_TRIGGER_WORDS: int = 200


# ── Rolling Claim History (session-scoped deduplication cache) ────────────────

class ClaimHistory:
    """
    Tracks the last N canonical claims dispatched to the LangGraph pipeline
    this session. Passed to classify_claim() so Gemini can detect semantic
    duplicates/paraphrases within the same API call — no extra round-trip.
    """

    MAX_SIZE: int = 10

    def __init__(self) -> None:
        self._claims: list[str] = []

    def recent(self) -> list[str]:
        return list(self._claims)

    def add(self, claim: str) -> None:
        self._claims.append(claim)
        if len(self._claims) > self.MAX_SIZE:
            self._claims.pop(0)


# ── Agent 1b: TranscriptBuffer ────────────────────────────────────────────────

class TranscriptBuffer:
    """
    Accumulates isFinal=True spoken words.

    - _buffer_words : words pending topic segmentation (may shrink via prepend_ongoing)
    - _session_words: ALL words spoken this session (never shrinks — used as full context)
    """

    def __init__(self) -> None:
        self._buffer_words: list[str] = []
        self._session_words: list[str] = []

    # ── Mutators ───────────────────────────────────────────────────────────────

    def add(self, text: str) -> None:
        """Append an isFinal=True utterance to both the buffer and session history."""
        words = text.strip().split()
        self._buffer_words.extend(words)
        self._session_words.extend(words)

    def prepend_ongoing(self, text: str) -> None:
        """
        Carry-forward an ONGOING TopicBlock so the next segmentation cycle
        begins with this text already in the buffer.
        NOTE: these words are already in session history — do NOT re-add.
        """
        words = text.strip().split()
        self._buffer_words = words + self._buffer_words

    def flush(self) -> str:
        """Return and clear the current buffer content."""
        text = " ".join(self._buffer_words)
        self._buffer_words = []
        return text

    # ── Queries ────────────────────────────────────────────────────────────────

    @property
    def buffer_word_count(self) -> int:
        return len(self._buffer_words)

    @property
    def should_trigger(self) -> bool:
        return self.buffer_word_count >= BUFFER_TRIGGER_WORDS

    @property
    def has_buffer_content(self) -> bool:
        return bool(self._buffer_words)

    def session_context(self) -> str:
        """Full session transcript — passed to classify_claim for reference resolution."""
        return " ".join(self._session_words)

    @property
    def total_session_words(self) -> int:
        return len(self._session_words)


# ── Layer 3: fact-check + send ────────────────────────────────────────────────

async def _fact_check_and_send(
    topic_text: str,
    session_context: str,
    ws: WebSocket,
    history: ClaimHistory,
) -> None:
    """
    Background coroutine: classify a COMPLETED topic block, run LangGraph
    pipeline if a checkable, non-duplicate claim is found, push result to Flutter.
    """
    topic_text = topic_text.strip()
    if not topic_text:
        return

    logger.info(
        "Fact-check dispatch — %d words: %r…",
        len(topic_text.split()),
        topic_text[:100],
    )

    try:
        claims = await asyncio.to_thread(
            extract_all_claims, topic_text, session_context, history.recent()
        )
    except Exception as exc:
        logger.exception("extract_all_claims error: %s", exc)
        return

    if not claims:
        logger.info("No verifiable claims found in topic block — skipped")
        return

    logger.info("Extracted %d claim(s) from topic block", len(claims))

    for claim_obj in claims:
        claim = claim_obj.get("claim", "").strip()
        if not claim:
            continue

        if claim_obj.get("is_duplicate", False):
            logger.info("Duplicate claim — silently discarded: %r", claim[:100])
            continue

        history.add(claim)
        logger.info("Claim → pipeline: %r", claim[:100])

        try:
            result = await asyncio.to_thread(run_pipeline_from_claim, claim)
        except Exception as exc:
            logger.exception("run_pipeline_from_claim error: %s", exc)
            continue

        if result:
            result["type"] = "result"
            try:
                await ws.send_text(json.dumps(result))
                logger.info(
                    "Result sent: verdict=%s confidence=%.2f",
                    result.get("claimVeracity"),
                    result.get("confidenceScore", 0.0),
                )
            except Exception:
                pass


# ── Layer 2: Agent 1b — topic-aware pump ──────────────────────────────────────

async def _run_segmentation_cycle(
    chunk: str,
    buffer: TranscriptBuffer,
    websocket: WebSocket,
    pending_tasks: set[asyncio.Task],
    history: ClaimHistory,
) -> None:
    """
    Single segmentation cycle:
    1. Call Gemini 2.0 Flash topic segmenter.
    2. Route each block:
       - COMPLETED → fire-and-forget fact-check task
       - ONGOING   → prepend back into the buffer
    """
    session_ctx = buffer.session_context()

    try:
        blocks = await asyncio.to_thread(segment_topics, chunk, session_ctx)
    except Exception as exc:
        logger.exception("segment_topics error — treating chunk as COMPLETED: %s", exc)
        # Zero-crash fallback: treat entire chunk as a single COMPLETED block
        from agents.topic_segmenter import TopicBlock
        blocks = [TopicBlock(topic_label="unknown", text=chunk, status="COMPLETED")]

    ongoing_count = sum(1 for b in blocks if not b.is_completed)
    completed_count = len(blocks) - ongoing_count
    logger.info(
        "Segmentation result: %d block(s) — %d COMPLETED, %d ONGOING",
        len(blocks), completed_count, ongoing_count,
    )

    for block in blocks:
        if block.is_completed:
            task = asyncio.create_task(
                _fact_check_and_send(block.text, session_ctx, websocket, history)
            )
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)
        else:
            # ONGOING — carry text forward into next 200-word cycle
            logger.info(
                "ONGOING topic %r (%d words) — prepending to buffer",
                block.topic_label, block.word_count,
            )
            buffer.prepend_ongoing(block.text)


async def _pump_transcript(
    queue: asyncio.Queue[tuple[str, bool] | None],
    buffer: TranscriptBuffer,
    websocket: WebSocket,
    pending_tasks: set[asyncio.Task],
    history: ClaimHistory,
) -> None:
    """Agent 1b — reads the queue, maintains TranscriptBuffer, triggers segmentation."""

    while True:
        item = await queue.get()

        if item is None:  # sentinel — ingestor finished
            break

        text, is_final = item

        # Only isFinal=True utterances go into the buffer — partials are noise
        if is_final and text.strip():
            buffer.add(text)
            logger.debug(
                "Buffer +%d words (total buffer: %d, session: %d)",
                len(text.split()), buffer.buffer_word_count, buffer.total_session_words,
            )

        # Trigger segmentation when buffer reaches 200 words
        if buffer.should_trigger:
            chunk = buffer.flush()
            logger.info(
                "Buffer trigger (%d words) — running topic segmentation",
                len(chunk.split()),
            )
            await _run_segmentation_cycle(chunk, buffer, websocket, pending_tasks, history)

    # ── Final flush on stop signal ────────────────────────────────────────────
    if buffer.has_buffer_content:
        chunk = buffer.flush()
        logger.info(
            "Final flush on stop (%d words) — running topic segmentation",
            len(chunk.split()),
        )
        await _run_segmentation_cycle(chunk, buffer, websocket, pending_tasks, history)


# ── Layer 1: WebSocket ingestor ───────────────────────────────────────────────

async def _ingest_ws(
    websocket: WebSocket,
    queue: asyncio.Queue[tuple[str, bool] | None],
) -> None:
    """
    Agent 1a — reads JSON text frames from Flutter WebSocket.
    Pushes (text, is_final) tuples → queue (both partials and finals).
    Sends sentinel None on stop or disconnect.
    """
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")

            if msg_type == "stop":
                logger.info("Stop signal received from Flutter")
                break

            if msg_type == "transcript_text":
                text = msg.get("text", "").strip()
                is_final = bool(msg.get("isFinal", True))
                if text:
                    logger.debug(
                        "Ingest (final=%s, %d words): %r",
                        is_final, len(text.split()), text[:60],
                    )
                    await queue.put((text, is_final))

    except WebSocketDisconnect:
        logger.info("Flutter WS disconnected")
    except Exception as exc:
        logger.exception("WS ingestor error: %s", exc)
    finally:
        await queue.put(None)  # sentinel


# ── WebSocket handler ─────────────────────────────────────────────────────────

@router.websocket("/ws/live-audit")
async def live_audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live Audit WS connected")

    queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()
    buffer = TranscriptBuffer()
    history = ClaimHistory()
    pending_tasks: set[asyncio.Task] = set()

    try:
        await asyncio.gather(
            _ingest_ws(websocket, queue),
            _pump_transcript(queue, buffer, websocket, pending_tasks, history),
        )
    except Exception as exc:
        logger.exception("Live Audit pipeline error: %s", exc)
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": str(exc)})
                )
        except Exception:
            pass

    finally:
        if pending_tasks:
            logger.info("Awaiting %d in-flight task(s)…", len(pending_tasks))
            await asyncio.gather(*list(pending_tasks), return_exceptions=True)

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps({"type": "done"}))
        except Exception:
            pass

        for task in list(pending_tasks):
            task.cancel()

        logger.info(
            "Live Audit WS session ended — total session words: %d, buffer trigger: %d words",
            buffer.total_session_words,
            BUFFER_TRIGGER_WORDS,
        )
