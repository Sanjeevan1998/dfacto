"""
Streaming transcription via Google Cloud Speech-to-Text v2 with Chirp model.

Architecture:
  Flutter (PCM audio) → WebSocket → this handler → Cloud Speech v2 streaming → WebSocket → Flutter

Setup required:
  1. Enable Cloud Speech-to-Text API on your GCP project
  2. Set GOOGLE_CLOUD_PROJECT=your-project-id in .env
  3. Either:
     a. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
     b. Run: gcloud auth application-default login
"""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.cloud.speech_v2 import SpeechAsyncClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions

router = APIRouter(tags=["transcribe"])
logger = logging.getLogger("dfacto.transcribe")

# Chirp requires a regional endpoint
_REGION = "us-central1"


@router.websocket("/ws/transcribe")
async def ws_transcribe(ws: WebSocket):
    """
    Streaming transcription with Google Chirp model.

    Protocol:
      Client → Server: binary PCM chunks (16kHz, 16-bit mono, little-endian)
      Server → Client: JSON  {"type": "transcript", "text": "...", "is_final": bool}
                    or  {"type": "error", "message": "..."}
    """
    await ws.accept()
    logger.info("Transcription WebSocket connected")

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project_id:
        await ws.send_json({"type": "error", "message": "GOOGLE_CLOUD_PROJECT not set in .env"})
        await ws.close()
        return

    # Connect to regional endpoint for Chirp
    try:
        client = SpeechAsyncClient(
            client_options=ClientOptions(
                api_endpoint=f"{_REGION}-speech.googleapis.com",
            )
        )
    except Exception as e:
        logger.error("Failed to create Speech client: %s", e)
        await ws.send_json({"type": "error", "message": f"Speech client init failed: {e}"})
        await ws.close()
        return

    recognizer = f"projects/{project_id}/locations/{_REGION}/recognizers/_"
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    # ── Recognition config ────────────────────────────────────────────────────

    recognition_config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            audio_channel_count=1,
        ),
        language_codes=["en-US"],
        model="chirp_2",
    )

    streaming_config = cloud_speech.StreamingRecognitionConfig(
        config=recognition_config,
        streaming_features=cloud_speech.StreamingRecognitionFeatures(
            interim_results=True,
        ),
    )

    # ── Request generator (feeds audio to Cloud Speech) ───────────────────────

    async def request_generator():
        # First request: config only (no audio)
        yield cloud_speech.StreamingRecognizeRequest(
            recognizer=recognizer,
            streaming_config=streaming_config,
        )
        # Subsequent requests: audio chunks from Flutter
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield cloud_speech.StreamingRecognizeRequest(audio=chunk)

    # ── Receive audio from Flutter WebSocket ──────────────────────────────────

    async def receive_audio():
        try:
            while True:
                data = await ws.receive_bytes()
                await audio_queue.put(data)
        except WebSocketDisconnect:
            logger.info("Client disconnected")
            await audio_queue.put(None)
        except Exception as e:
            logger.error("Audio receive error: %s", e)
            await audio_queue.put(None)

    # ── Send transcription results back to Flutter ────────────────────────────

    async def send_transcriptions():
        try:
            responses = await client.streaming_recognize(
                requests=request_generator()
            )
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = result.alternatives[0].transcript
                    is_final = result.is_final
                    logger.info(
                        "Transcript (%s): %s",
                        "final" if is_final else "interim",
                        transcript[:80],
                    )
                    try:
                        await ws.send_json({
                            "type": "transcript",
                            "text": transcript,
                            "is_final": is_final,
                        })
                    except Exception:
                        break
        except Exception as e:
            logger.error("Streaming recognition error: %s", e)
            try:
                await ws.send_json({
                    "type": "error",
                    "message": str(e),
                })
            except Exception:
                pass

    # ── Run both loops concurrently ───────────────────────────────────────────

    try:
        await asyncio.gather(
            receive_audio(),
            send_transcriptions(),
        )
    except Exception as e:
        logger.error("Transcription session error: %s", e)
    finally:
        logger.info("Transcription session ended")
        try:
            await ws.close()
        except Exception:
            pass
