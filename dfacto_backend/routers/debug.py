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
            model="gemini-2.5-flash",
            contents=extract_prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=400,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        import json, re
        raw = response.text.strip()
        s, e = raw.find("["), raw.rfind("]")
        if s != -1 and e != -1:
            raw = raw[s : e + 1]
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


# ── Follow-up Q&A endpoint ───────────────────────────────────────────────────

class FollowupRequest(BaseModel):
    claim: str       # The original fact-checked claim
    question: str    # User's follow-up question
    context: str = ""  # Optional: verdict/summary for richer answers


@router.post("/followup")
async def debug_followup(body: FollowupRequest):
    """
    Answer a follow-up question about a fact-checked claim.
    Uses raw Tavily (no per-result Gemini stance calls) + single Gemini synthesis.

    Example:
        curl -X POST http://localhost:8000/debug/followup \\
             -H 'Content-Type: application/json' \\
             -d '{"claim": "Vaccines cause autism", "question": "What does the CDC say?"}'
    """
    import asyncio
    import os
    from google import genai
    from google.genai import types as genai_types
    from langchain_tavily import TavilySearch

    question = body.question.strip()
    claim = body.claim.strip()
    if not question or not claim:
        return {"answer": ""}

    logger.info("Follow-up question for claim %r: %r", claim[:80], question[:80])

    # Raw Tavily search — no per-result Gemini stance calls, much faster
    search_q = f"{claim[:60]} {question[:60]}"
    raw_results = []
    tavily_answer = ""
    try:
        tool = TavilySearch(
            max_results=4,
            search_depth="basic",
            include_answer=True,
            include_raw_content=False,
        )
        response = await asyncio.to_thread(tool.invoke, {"query": search_q})
        if isinstance(response, dict):
            raw_results = response.get("results", [])
            tavily_answer = response.get("answer", "") or ""
    except Exception as exc:
        logger.warning("Tavily follow-up search failed: %s", exc)

    # Build evidence string from raw Tavily content (no extra Gemini calls per result)
    parts = []
    if tavily_answer:
        parts.append(f"[Web summary] {tavily_answer[:400]}")
    for r in raw_results[:3]:
        src = r.get("url", "")
        content = (r.get("content") or "").strip()[:300]
        if content:
            parts.append(f"[{src}] {content}")
    excerpts = "\n".join(parts) or "No additional sources found."

    # Single Gemini call to synthesize the answer
    prompt = f"""You are a fact-check assistant. Answer the follow-up question below concisely (2-4 sentences max).
Use the provided evidence and original claim context. Be direct and factual. No markdown.

Original claim: "{claim}"
{f'Fact-check context: {body.context}' if body.context else ''}

Follow-up question: "{question}"

Evidence:
{excerpts}

Answer (plain text only, 2-4 sentences):"""

    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=200,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        answer = response.text.strip()
        if not answer:
            answer = "No answer found."
    except Exception as exc:
        logger.warning("Follow-up Gemini error: %s", exc)
        answer = "Unable to retrieve an answer at this time."

    logger.info("Follow-up answer: %r", answer[:100])
    return {"answer": answer}
