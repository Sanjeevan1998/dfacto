"""
Debug router — bypass Gemini audio transcription for direct pipeline testing.

Endpoints:
  POST /debug/check   → inject a plain-text claim directly into the LangGraph pipeline
  GET  /debug/logs    → return last N structured log lines
"""

from __future__ import annotations

import logging
from collections import deque

from fastapi import APIRouter
from pydantic import BaseModel

from agents.supervisor import run_pipeline_from_claim
from agents.claim_classifier import classify_claim

router = APIRouter(prefix="/debug", tags=["debug"])
logger = logging.getLogger("dfacto.debug")

# ── In-memory log ring buffer (last 200 lines) ──────────────────────────────

_LOG_BUFFER: deque[str] = deque(maxlen=200)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _LOG_BUFFER.append(self.format(record))


_handler = _BufferHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s"))
logging.getLogger("dfacto").addHandler(_handler)


# ── Request / Response models ────────────────────────────────────────────────

class ClaimRequest(BaseModel):
    claim: str

class TextRequest(BaseModel):
    text: str  # Raw spoken phrase to classify before fact-checking


class DebugLogsResponse(BaseModel):
    lines: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/check")
async def debug_check(body: ClaimRequest):
    """
    Inject a plain-text claim directly into the LangGraph pipeline,
    bypassing Gemini audio transcription entirely.

    Example:
        curl -X POST http://localhost:8000/debug/check \\
             -H 'Content-Type: application/json' \\
             -d '{"claim": "The Earth is flat"}'
    """
    logger.info("Debug check — claim: %r", body.claim)
    result = run_pipeline_from_claim(body.claim)
    if result is None:
        return {"status": "no_result", "reason": "empty claim or pipeline error"}
    return result


@router.get("/logs")
async def debug_logs(n: int = 50):
    """Return the last N log lines from the dfacto logger."""
    lines = list(_LOG_BUFFER)[-n:]
    return {"lines": lines}


@router.post("/classify")
async def debug_classify(body: TextRequest):
    """
    Agent 0: classify whether a spoken phrase is a verifiable claim.
    Returns: {is_claim, needs_context, extracted_claim, source}
    """
    import asyncio
    result = await asyncio.to_thread(classify_claim, body.text)
    return result


class TranscriptRequest(BaseModel):
    transcript: str  # 30-second rolling transcript window


@router.post("/analyze")
async def debug_analyze(body: TranscriptRequest):
    """
    Rolling-window batch analysis for news/podcast mode.
    Extracts ALL distinct checkable claims from a transcript window,
    fact-checks each one, and returns a unified list of results.
    """
    import asyncio
    import os
    from google import genai
    from google.genai import types as genai_types

    transcript = body.transcript.strip()
    if not transcript:
        return {"claims": []}

    logger.info("Batch analyze: %d chars of transcript", len(transcript))

    # Step 1: Extract all distinct claims from the transcript window
    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        extract_prompt = f"""Extract all distinct verifiable factual claims from this transcript.
Return ONLY a JSON array of standalone declarative sentences (no filler/opinions).
Example: ["Vaccines cause autism", "Neil Armstrong walked on the Moon in 1969"]

Transcript:
{transcript}"""
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=extract_prompt,
            config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=400),
        )
        import json, re
        raw = re.sub(r"^```[a-z]*\n?", "", response.text.strip()).rstrip("```").strip()
        claims_list = json.loads(raw)
        if not isinstance(claims_list, list):
            claims_list = []
    except Exception as exc:
        logger.warning("Batch claim extraction failed: %s", exc)
        return {"claims": []}

    if not claims_list:
        return {"claims": []}

    logger.info("Batch: extracted %d claims", len(claims_list))

    # Step 2: Fact-check each claim concurrently (max 3 to avoid rate limits)
    async def check_one(claim: str):
        try:
            result = await asyncio.to_thread(run_pipeline_from_claim, claim)
            return result
        except Exception:
            return None

    tasks = [check_one(c) for c in claims_list[:3]]  # cap at 3
    results = await asyncio.gather(*tasks)
    valid = [r for r in results if r is not None]
    return {"claims": valid}
