"""
WebSocket router for the Live Audit pipeline.

Route: WS /ws/live-audit
- Accepts binary PCM audio frames streaming from the Flutter app.
- Buffers chunks until a 3-second window is reached.
- Phase 1: Runs Gemini transcription → immediately sends {"type":"transcript"} message.
- Phase 2: Runs LangGraph workers → sends {"type":"result"} message with fact-check verdict.
- Continues listening immediately for the next audio buffer.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.agent1_extractor import extract_claim
from agents.claim_classifier import classify_claim
from agents.supervisor import run_pipeline_from_claim

logger = logging.getLogger("dfacto.live_audit")

router = APIRouter()

# Buffer ~3 seconds at 16 kHz, 16-bit mono = 96 000 bytes
_BUFFER_TARGET_BYTES = 96_000


@router.websocket("/ws/live-audit")
async def live_audit_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info("Live Audit WebSocket connected.")
    buffer = bytearray()

    try:
        while True:
            data = await websocket.receive_bytes()
            buffer.extend(data)

            if len(buffer) >= _BUFFER_TARGET_BYTES:
                chunk = bytes(buffer[:_BUFFER_TARGET_BYTES])
                buffer = buffer[_BUFFER_TARGET_BYTES:]

                # ── Phase 1: Transcribe immediately ──────────────────────────
                extraction = await asyncio.to_thread(extract_claim, chunk)
                transcript = extraction.get("transcript", "").strip()
                core_claim = extraction.get("core_claim", "").strip()

                if transcript:
                    # ── Agent 0: Classify whether transcript contains a checkable claim ──
                    classification = await asyncio.to_thread(classify_claim, transcript)
                    is_claim = classification.get("is_claim", False)
                    needs_context = classification.get("needs_context", False)
                    extracted = classification.get("extracted_claim", "").strip()
                    logger.info(
                        "Classifier: is_claim=%s needs_context=%s source=%s claim=%r",
                        is_claim, needs_context, classification.get("source"), extracted[:60],
                    )

                    # Send transcript immediately so UI can show it
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript,
                        "claim": extracted or core_claim,
                        "needsContext": needs_context,
                    }))
                    logger.info("Transcript sent: %r", transcript[:80])

                    # ── Phase 2: Fact-check only if classifier confirms a verifiable claim ──
                    if is_claim and not needs_context:
                        claim_to_check = extracted or core_claim
                        result = await asyncio.to_thread(run_pipeline_from_claim, claim_to_check)
                        if result:
                            result["type"] = "result"
                            await websocket.send_text(json.dumps(result))
                            logger.info(
                                "Result sent: verdict=%s confidence=%.2f",
                                result.get("claimVeracity"),
                                result.get("confidenceScore", 0.0),
                            )

    except WebSocketDisconnect:
        logger.info("Live Audit WebSocket disconnected.")
    except Exception as exc:
        logger.exception("Unhandled error in Live Audit WS: %s", exc)
        await websocket.close(code=1011)
