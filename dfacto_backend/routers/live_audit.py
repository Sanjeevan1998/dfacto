"""
WebSocket router — Live Audit pipeline (Phase 3: Gemini Live API).

Route: WS /ws/live-audit

Protocol
--------
Flutter → Backend  : binary  PCM frames (16 kHz, 16-bit mono LE), streamed continuously
Flutter → Backend  : text    {"type":"stop"}   when user presses Stop
Backend → Flutter  : text    {"type":"transcript","text":"<token>","isPartial":true}
Backend → Flutter  : text    {"type":"result",...}   FactCheckResult when a claim is verified
Backend → Flutter  : text    {"type":"done"}          after buffer flush on Stop
Backend → Flutter  : text    {"type":"error","message":"..."}  on fatal session error

Architecture
------------
1. Open a Gemini Live session (native audio model) in transcription-only mode.
2. pump_audio(): receive PCM from Flutter → forward to Gemini in real-time.
3. pump_transcript(): receive transcript tokens from Gemini → send to Flutter immediately
   AND accumulate in a rolling 25-word buffer.
4. Every 25 new words (max 50), run claim_classifier:
   - is_claim + no context needed → run_pipeline_from_claim → send result to Flutter,
     reset buffer keeping last 5 words for continuity.
   - otherwise → keep accumulating, try again at next 25-word increment.
5. On {"type":"stop"}: drain remaining Gemini tokens (2s grace), flush buffer, send "done".
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from agents.claim_classifier import classify_claim
from agents.supervisor import run_pipeline_from_claim

logger = logging.getLogger("dfacto.live_audit")

router = APIRouter()

# Native audio model gives best real-time transcription quality.
# Override via GEMINI_LIVE_MODEL env var if needed.
_MODEL = os.getenv(
    "GEMINI_LIVE_MODEL",
    "gemini-2.5-flash-native-audio-preview-12-2025",
)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            # v1alpha required for native audio preview models
            http_options=types.HttpOptions(api_version="v1alpha"),
        )
    return _client


# ── Rolling transcript buffer ──────────────────────────────────────────────────

class TranscriptBuffer:
    """
    Accumulates streaming transcript tokens word by word.

    Triggers a claim-check every CHUNK_WORDS new words so the context window
    grows organically. If no claim is found, keeps all words and tries again
    at the next increment. Forces a check at MAX_WORDS. After a successful
    claim extraction, retains TAIL_WORDS for natural continuity into the next window.
    """

    CHUNK_WORDS: int = 25
    MAX_WORDS: int = 50
    TAIL_WORDS: int = 5

    def __init__(self) -> None:
        self._words: list[str] = []
        self._words_since_check: int = 0

    def add(self, token: str) -> None:
        new = token.split()
        self._words.extend(new)
        self._words_since_check += len(new)

    @property
    def should_check(self) -> bool:
        return (
            self._words_since_check >= self.CHUNK_WORDS
            or len(self._words) >= self.MAX_WORDS
        )

    @property
    def has_content(self) -> bool:
        return bool(self._words)

    def text(self) -> str:
        return " ".join(self._words)

    def consume(self) -> None:
        """Claim confirmed — keep tail for next window continuity."""
        self._words = self._words[-self.TAIL_WORDS :]
        self._words_since_check = 0

    def reset_check_counter(self) -> None:
        """No claim yet — keep all words, reset chunk counter."""
        self._words_since_check = 0

    def clear(self) -> None:
        self._words.clear()
        self._words_since_check = 0


# ── Claim-check helper ─────────────────────────────────────────────────────────

async def _check_buffer(buffer: TranscriptBuffer, ws: WebSocket) -> bool:
    """
    Classify buffer text; if it contains a verifiable claim, run the supervisor
    pipeline and push the FactCheckResult to Flutter.
    Returns True if a claim was processed and the buffer was consumed.
    """
    text = buffer.text().strip()
    if not text:
        buffer.reset_check_counter()
        return False

    logger.info("Buffer check: %d words — %r…", len(buffer._words), text[:80])

    classification = await asyncio.to_thread(classify_claim, text)
    is_claim = classification.get("is_claim", False)
    needs_context = classification.get("needs_context", False)

    if is_claim and not needs_context:
        claim = classification.get("extracted_claim", "").strip() or text
        logger.info("Claim confirmed — running pipeline: %r", claim[:80])

        result = await asyncio.to_thread(run_pipeline_from_claim, claim)
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

        buffer.consume()
        return True

    logger.info(
        "No claim yet (is_claim=%s needs_context=%s) — accumulating",
        is_claim, needs_context,
    )
    buffer.reset_check_counter()
    return False


# ── WebSocket handler ──────────────────────────────────────────────────────────

@router.websocket("/ws/live-audit")
async def live_audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live Audit WS connected — model=%s", _MODEL)

    buffer = TranscriptBuffer()
    stop_event = asyncio.Event()

    live_config = {
        # Text output only — we want transcription, not audio responses
        "response_modalities": ["TEXT"],
        # Surface the user's spoken audio as input_transcription tokens
        "input_audio_transcription": {},
        # Prevent the model from responding conversationally
        "system_instruction": (
            "You are a real-time transcription engine. "
            "Listen to the audio and output only a verbatim transcription of the "
            "spoken words. Do not respond, comment, or add anything else."
        ),
        # Low end-of-speech sensitivity avoids premature cuts mid-sentence
        "realtime_input_config": {
            "automatic_activity_detection": {
                "disabled": False,
                "end_of_speech_sensitivity": types.EndSensitivity.END_SENSITIVITY_LOW,
                "silence_duration_ms": 500,
            }
        },
    }

    try:
        client = _get_client()

        async with client.aio.live.connect(model=_MODEL, config=live_config) as session:
            logger.info("Gemini Live session established")

            # ── Task 1: Flutter PCM → Gemini ──────────────────────────────────

            async def pump_audio() -> None:
                """Forward raw PCM chunks from Flutter to the Gemini Live session."""
                try:
                    while not stop_event.is_set():
                        # Use the raw ASGI receive dict so we can handle both
                        # binary (audio) and text (control) messages in one loop.
                        msg = await websocket.receive()

                        if msg["type"] == "websocket.disconnect":
                            stop_event.set()
                            break

                        if msg["type"] != "websocket.receive":
                            continue

                        if msg.get("bytes"):
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=msg["bytes"],
                                    mime_type="audio/pcm;rate=16000",
                                )
                            )
                        elif msg.get("text"):
                            try:
                                ctrl = json.loads(msg["text"])
                                if ctrl.get("type") == "stop":
                                    logger.info("Stop signal from Flutter")
                                    stop_event.set()
                                    break
                            except (json.JSONDecodeError, AttributeError):
                                pass

                except WebSocketDisconnect:
                    stop_event.set()
                except Exception as exc:
                    logger.exception("pump_audio error: %s", exc)
                    stop_event.set()

            # ── Task 2: Gemini tokens → Flutter + rolling buffer ───────────────

            async def pump_transcript() -> None:
                """
                Stream transcript tokens from Gemini → Flutter (live word display),
                accumulate into rolling buffer, trigger claim detection at thresholds.
                """
                try:
                    async for msg in session.receive():
                        if stop_event.is_set():
                            break

                        # Extract input transcription token
                        token: str | None = None
                        try:
                            sc = msg.server_content
                            if sc and sc.input_transcription and sc.input_transcription.text:
                                token = sc.input_transcription.text
                        except AttributeError:
                            pass

                        if not token:
                            continue

                        buffer.add(token)

                        # Push token to Flutter for word-by-word live display
                        try:
                            await websocket.send_text(
                                json.dumps({
                                    "type": "transcript",
                                    "text": token,
                                    "isPartial": True,
                                })
                            )
                        except Exception:
                            break

                        # Check buffer at every 25-word / 50-word-max threshold
                        if buffer.should_check:
                            await _check_buffer(buffer, websocket)

                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    if not stop_event.is_set():
                        logger.exception("pump_transcript error: %s", exc)

            # ── Lifecycle: audio pump controls session duration ────────────────

            t_audio = asyncio.create_task(pump_audio())
            t_transcript = asyncio.create_task(pump_transcript())

            # Wait for Stop (or disconnect) from Flutter
            await t_audio

            # Give Gemini 2 s to deliver any remaining transcript tokens
            try:
                await asyncio.wait_for(t_transcript, timeout=2.0)
            except asyncio.TimeoutError:
                t_transcript.cancel()
                try:
                    await t_transcript
                except asyncio.CancelledError:
                    pass

            # ── Flush remaining buffer ─────────────────────────────────────────

            if buffer.has_content:
                logger.info("Flushing %d buffered words after stop", len(buffer._words))
                await _check_buffer(buffer, websocket)

            # Signal Flutter that all processing is complete
            try:
                await websocket.send_text(json.dumps({"type": "done"}))
            except Exception:
                pass

    except WebSocketDisconnect:
        logger.info("Live Audit WS disconnected before session started")
    except Exception as exc:
        logger.exception("Live Audit WS fatal error: %s", exc)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(exc)})
            )
        except Exception:
            pass
    finally:
        logger.info("Live Audit WS session ended")
