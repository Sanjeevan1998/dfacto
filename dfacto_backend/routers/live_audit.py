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

Architecture (3 concurrent layers)
------------
Layer 1 — Device STT (Flutter, on-device)
    speech_to_text package transcribes audio word-by-word on the device.
    Partial results → live display in UI instantly (no backend round-trip).
    Final results (utterance complete) → sent to backend via WebSocket.

Layer 2 — TranscriptBuffer (Backend, this file)
    Receives final utterance texts from Flutter.
    Accumulates in rolling buffer.
    Fires Layer 3 as a background task when:
        a) An utterance completes (isFinal=True) and buffer has >= MIN_WORDS, OR
        b) Buffer hits CHUNK_WORDS (word-count fallback), OR
        c) Buffer hits MAX_WORDS (hard cap).
    Never blocks — transcript continues flowing while fact-checking runs.

Layer 3 — _fact_check_and_send() [background asyncio.Task per window]
    classify_claim() → is there a verifiable claim?
    run_pipeline_from_claim() → DDG + Snopes/PolitiFact workers in parallel.
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


# ── Rolling transcript buffer ──────────────────────────────────────────────────

class TranscriptBuffer:
    """
    Accumulates final utterance texts word by word.
    Designed for fire-and-forget concurrent fact-checking.
    """

    CHUNK_WORDS: int = 30        # Word-count trigger for fact-check
    MAX_WORDS: int = 60          # Hard cap — always fire
    TAIL_WORDS: int = 10         # Words kept after consume() for cross-window continuity
    MIN_WORDS_TO_CHECK: int = 8  # Minimum before firing on utterance boundary

    def __init__(self) -> None:
        self._words: list[str] = []
        self._words_since_check: int = 0

    def add(self, text: str) -> None:
        new = text.strip().split()
        self._words.extend(new)
        self._words_since_check += len(new)

    @property
    def word_count(self) -> int:
        return len(self._words)

    @property
    def has_content(self) -> bool:
        return bool(self._words)

    @property
    def should_check_on_count(self) -> bool:
        return (
            self._words_since_check >= self.CHUNK_WORDS
            or len(self._words) >= self.MAX_WORDS
        )

    def ready_for_utterance_check(self) -> bool:
        return self._words_since_check >= self.MIN_WORDS_TO_CHECK

    def snapshot(self) -> str:
        return " ".join(self._words)

    def consume(self) -> None:
        """Keep tail for continuity; reset counter."""
        self._words = self._words[-self.TAIL_WORDS:]
        self._words_since_check = 0

    def clear(self) -> None:
        self._words.clear()
        self._words_since_check = 0


# ── Layer 3: background fact-check task ───────────────────────────────────────

async def _fact_check_and_send(text: str, ws: WebSocket) -> None:
    """
    Background coroutine: classify text, run pipeline if claim found,
    push result to Flutter. Runs concurrently — never blocks transcript display.
    """
    text = text.strip()
    if not text:
        return

    logger.info("Fact-check window (%d words): %r…", len(text.split()), text[:100])

    try:
        classification = await asyncio.to_thread(classify_claim, text)
    except Exception as exc:
        logger.exception("classify_claim error: %s", exc)
        return

    is_claim = classification.get("is_claim", False)
    needs_context = classification.get("needs_context", False)

    if not (is_claim and not needs_context):
        logger.info(
            "No actionable claim (is_claim=%s needs_context=%s) — window skipped",
            is_claim, needs_context,
        )
        return

    claim = classification.get("extracted_claim", "").strip() or text
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


# ── WebSocket handler ──────────────────────────────────────────────────────────

@router.websocket("/ws/live-audit")
async def live_audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live Audit WS connected")

    buffer = TranscriptBuffer()
    pending_tasks: set[asyncio.Task] = set()

    def _fire_check(snapshot: str) -> None:
        if not snapshot.strip():
            return
        task = asyncio.create_task(_fact_check_and_send(snapshot, websocket))
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)

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
            buffer.add(text)

            # ── Fire background fact-check (never block) ───────────────────────
            if buffer.should_check_on_count:
                logger.info(
                    "Word-count trigger (%d words) — firing fact-check",
                    buffer.word_count,
                )
                snapshot = buffer.snapshot()
                buffer.consume()
                _fire_check(snapshot)

            elif is_final and buffer.ready_for_utterance_check():
                logger.info(
                    "Utterance boundary (%d words) — firing fact-check",
                    buffer.word_count,
                )
                snapshot = buffer.snapshot()
                buffer.consume()
                _fire_check(snapshot)

    except WebSocketDisconnect:
        logger.info("Live Audit WS disconnected")
    except Exception as exc:
        logger.exception("Live Audit WS error: %s", exc)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass
    finally:
        # Final flush of any remaining buffer
        if buffer.has_content:
            logger.info("Final flush: %d words", buffer.word_count)
            _fire_check(buffer.snapshot())

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

        logger.info("Live Audit WS session ended")
