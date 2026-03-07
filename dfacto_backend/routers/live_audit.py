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
                    # Send transcript text immediately so UI can show it
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript,
                        "claim": core_claim,
                    }))
                    logger.info("Transcript sent: %r (claim: %r)", transcript[:80], core_claim)

                # ── Phase 2: Fact-check if a claim was found ──────────────────
                if core_claim:
                    result = await asyncio.to_thread(run_pipeline_from_claim, core_claim)
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
