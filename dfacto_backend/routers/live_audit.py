"""
WebSocket router for the Live Audit pipeline.

Route: WS /ws/live-audit
- Accepts binary PCM audio frames streamed from the Flutter app.
- Buffers chunks until a minimum window is reached.
- Passes the buffer to the LangGraph supervisor pipeline.
- Sends back a JSON FactCheckResult payload per detected claim.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.supervisor import run_pipeline

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

                # Run the LangGraph pipeline off-thread (non-blocking)
                result = await asyncio.to_thread(run_pipeline, chunk)

                if result:
                    await websocket.send_text(json.dumps(result))
                    logger.info(
                        "Sent fact-check result: verdict=%s confidence=%.2f",
                        result.get("verdict"),
                        result.get("confidenceScore", 0.0),
                    )

    except WebSocketDisconnect:
        logger.info("Live Audit WebSocket disconnected.")
    except Exception as exc:
        logger.exception("Unhandled error in Live Audit WS: %s", exc)
        await websocket.close(code=1011)
