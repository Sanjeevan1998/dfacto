"""
Agent 1 — Transcription & Claim Extraction

Sends a raw PCM audio buffer to Gemini, returns a transcript and
the single most important factual claim found in the audio.
Falls back gracefully if no claim is detectable.
"""

from __future__ import annotations

import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger("dfacto.agent1")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
        _client = genai.Client(api_key=api_key)
    return _client


_EXTRACTION_PROMPT = """
You are a precise fact-checking assistant.

You have been given an audio clip. Do the following:
1. Transcribe the audio verbatim.
2. Identify if there is a single, specific, verifiable factual claim in the transcript.
   - A valid claim is a concrete assertion (e.g., "GDP grew by 4%", "Vaccines cause autism").
   - Opinions, questions, and vague statements are NOT claims.
3. Return ONLY valid JSON in this exact format (no markdown, no explanation):

{
  "transcript": "<full verbatim transcript>",
  "core_claim": "<isolated claim sentence, or empty string if none found>"
}
"""


def extract_claim(audio_bytes: bytes) -> dict[str, str]:
    """
    Sends audio_bytes to Gemini and returns {"transcript": ..., "core_claim": ...}.
    Returns empty strings on failure so the pipeline can short-circuit gracefully.
    """
    if not audio_bytes:
        return {"transcript": "", "core_claim": ""}

    try:
        client = _get_client()

        # Upload audio inline as raw bytes (WAV/PCM, 16kHz 16-bit mono)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/wav",
                ),
                _EXTRACTION_PROMPT,
            ],
        )

        raw = response.text.strip()
        # Strip markdown code fences if Gemini adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)
        return {
            "transcript": parsed.get("transcript", ""),
            "core_claim": parsed.get("core_claim", ""),
        }

    except json.JSONDecodeError as exc:
        logger.warning("Agent 1: JSON parse error — %s", exc)
        return {"transcript": "", "core_claim": ""}
    except Exception as exc:
        logger.exception("Agent 1: Gemini call failed — %s", exc)
        return {"transcript": "", "core_claim": ""}
