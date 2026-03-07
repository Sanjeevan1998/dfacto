"""
WebSocket router — Live Audit pipeline.

Route: WS /ws/live-audit

Protocol
--------
Flutter → Backend  : text  {"type":"transcript_text","text":"...","isFinal":true/false}
Flutter → Backend  : text  {"type":"stop"}
Backend → Flutter  : text  {"type":"result",...}   FactCheckResult when claim verified
Backend → Flutter  : text  {"type":"done"}          after stop + all tasks finish
Backend → Flutter  : text  {"type":"error","message":"..."}  on fatal error

Architecture (3-layer pipeline)
--------------------------------
Layer 1 — Agent 1a (WS Ingestor)
    Dedicated strictly to the WebSocket receive loop.
    Pushes each final utterance text into an asyncio.Queue.
    Zero dropped words — the queue decouples receipt from processing.

Layer 2 — Agent 1b (Context & Meaning Accumulator)
    pump_transcript() coroutine reads from the queue.
    Maintains a ContextWindow: ALL words spoken this session are kept.
    Never discards spoken words — uses _check_from_idx pointer to know
    which words are "new since last check".
    Fires Layer 3 as a fire-and-forget asyncio.Task when:
        a) Enough new words have arrived since last check (CHUNK_WORDS), OR
        b) An utterance boundary arrives and MIN_NEW_WORDS threshold met.
    Transcript continues flowing while fact-checking runs concurrently.

Layer 3 — Agent 1c → pipeline [background asyncio.Task per window]
    classify_claim(new_window, full_context) → is there a verifiable claim?
    run_pipeline_from_claim(claim) → workers in parallel.
    Sends {"type":"result",...} to Flutter when done.
    Multiple instances run concurrently across overlapping windows.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.claim_classifier import classify_claim
from agents.supervisor import run_pipeline_from_claim

logger = logging.getLogger("dfacto.live_audit")

router = APIRouter()


# ── Agent 1b: Context Window (NEVER discards session words) ───────────────────

class ContextWindow:
    """
    Accumulates ALL words spoken in the session.
    Never removes words — uses _check_from_idx to track which words
    are new since the last fact-check trigger.
    """

    CHUNK_NEW_WORDS: int = 30   # Trigger fact-check after this many new words
    MIN_NEW_WORDS: int = 8      # Minimum new words before firing on utterance boundary

    def __init__(self) -> None:
        self._words: list[str] = []       # Full session transcript (never shrinks)
        self._check_from_idx: int = 0     # Index of first word not yet checked

    def add(self, text: str) -> None:
        self._words.extend(text.strip().split())

    @property
    def total_words(self) -> int:
        return len(self._words)

    @property
    def new_word_count(self) -> int:
        return len(self._words) - self._check_from_idx

    @property
    def has_new_content(self) -> bool:
        return self.new_word_count > 0

    @property
    def should_check_on_count(self) -> bool:
        return self.new_word_count >= self.CHUNK_NEW_WORDS

    def ready_for_utterance_check(self) -> bool:
        return self.new_word_count >= self.MIN_NEW_WORDS

    def new_window_snapshot(self) -> str:
        """The words added since the last check (what's new)."""
        return " ".join(self._words[self._check_from_idx:])

    def full_context_snapshot(self) -> str:
        """The entire session transcript so far."""
        return " ".join(self._words)

    def advance_check_pointer(self) -> None:
        """Mark all current words as checked. Words are NEVER deleted."""
        self._check_from_idx = len(self._words)

    @property
    def has_content(self) -> bool:
        return bool(self._words)


# ── Layer 3: background fact-check task ───────────────────────────────────────

async def _fact_check_and_send(
    new_window: str,
    full_context: str,
    ws: WebSocket,
) -> None:
    """
    Background coroutine: classify the new window (with full context),
    run pipeline if a claim is found, push result to Flutter.
    Runs concurrently — never blocks the transcript ingestor.
    """
    new_window = new_window.strip()
    if not new_window:
        return

    logger.info(
        "Fact-check window (%d new words, %d total context): %r…",
        len(new_window.split()),
        len(full_context.split()),
        new_window[:100],
    )

    try:
        classification = await asyncio.to_thread(classify_claim, new_window, full_context)
    except Exception as exc:
        logger.exception("classify_claim error: %s", exc)
        return

    is_claim = classification.get("is_claim", False)
    needs_context = classification.get("needs_context", False)

    if not (is_claim and not needs_context):
        logger.info(
            "No actionable claim (is_claim=%s needs_context=%s) — window skipped",
            is_claim,
            needs_context,
        )
        return

    claim = classification.get("extracted_claim", "").strip() or new_window
    logger.info("Claim extracted — running pipeline: %r", claim[:100])

    try:
        result = await asyncio.to_thread(run_pipeline_from_claim, claim)
    except Exception as exc:
        logger.exception("run_pipeline_from_claim error: %s", exc)
        return

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


# ── Agent 1a: WS Ingestor → asyncio.Queue ─────────────────────────────────────

async def _ingest_ws(
    websocket: WebSocket,
    queue: asyncio.Queue[tuple[str, bool] | None],
) -> None:
    """
    Agent 1a — dedicated WS receive loop.
    Pushes (text, is_final) tuples into the queue.
    Sends None sentinel to signal stop.
    """
    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "stop":
                logger.info("Stop signal received")
                break

            if msg_type != "transcript_text":
                continue

            text = msg.get("text", "").strip()
            is_final = bool(msg.get("isFinal", False))

            if not text:
                continue

            logger.info("Transcript text (isFinal=%s): %r", is_final, text[:100])
            await queue.put((text, is_final))

    except WebSocketDisconnect:
        logger.info("Live Audit WS disconnected during ingest")
    except Exception as exc:
        logger.exception("WS ingest error: %s", exc)
    finally:
        await queue.put(None)  # sentinel → pump_transcript exits


# ── Agent 1b: Context Accumulator + fire-and-forget trigger ───────────────────

async def _pump_transcript(
    queue: asyncio.Queue[tuple[str, bool] | None],
    context: ContextWindow,
    websocket: WebSocket,
    pending_tasks: set[asyncio.Task],
) -> None:
    """
    Agent 1b — reads queue, builds the never-discarding ContextWindow,
    fires fact-check tasks at the right moments.
    """

    def _fire_check() -> None:
        new_window = context.new_window_snapshot()
        full_ctx = context.full_context_snapshot()
        if not new_window.strip():
            return
        context.advance_check_pointer()
        task = asyncio.create_task(
            _fact_check_and_send(new_window, full_ctx, websocket)
        )
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)

    while True:
        item = await queue.get()

        if item is None:  # sentinel — WS ingestor finished
            break

        text, is_final = item
        context.add(text)

        if context.should_check_on_count:
            logger.info(
                "Word-count trigger (%d new words) — firing fact-check",
                context.new_word_count,
            )
            _fire_check()

        elif is_final and context.ready_for_utterance_check():
            logger.info(
                "Utterance boundary (%d new words) — firing fact-check",
                context.new_word_count,
            )
            _fire_check()

    # Final flush: any remaining new words after stop
    if context.has_new_content:
        logger.info("Final flush: %d new words", context.new_word_count)
        _fire_check()


# ── WebSocket handler ──────────────────────────────────────────────────────────

@router.websocket("/ws/live-audit")
async def live_audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live Audit WS connected")

    queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()
    context = ContextWindow()
    pending_tasks: set[asyncio.Task] = set()

    try:
        # Run Agent 1a and Agent 1b concurrently
        await asyncio.gather(
            _ingest_ws(websocket, queue),
            _pump_transcript(queue, context, websocket, pending_tasks),
        )
    except Exception as exc:
        logger.exception("Live Audit WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
    finally:
        # Wait for all in-flight fact-check tasks
        if pending_tasks:
            logger.info("Awaiting %d in-flight task(s)…", len(pending_tasks))
            await asyncio.gather(*list(pending_tasks), return_exceptions=True)

        try:
            await websocket.send_text(json.dumps({"type": "done"}))
        except Exception:
            pass

        for task in list(pending_tasks):
            task.cancel()

        logger.info(
            "Live Audit WS session ended — total words captured: %d",
            context.total_words,
        )
