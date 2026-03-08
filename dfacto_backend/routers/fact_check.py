"""
Fact-Check Microservice — the pure engine layer.

This module has ZERO knowledge of WebSockets, audio streams, or UI transport.
Any feature tab (Live Audit, Interactive, Scanner, Radar…) can call
`process_fact_check(request)` directly, or hit the HTTP endpoint below.

Routes
------
POST /fact-check   →  FactCheckRequest → FactCheckResponse
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from models.fact_check import FactCheckRequest, FactCheckResponse
from agents.supervisor import run_pipeline_from_claim

logger = logging.getLogger("dfacto.fact_check")

router = APIRouter(prefix="/fact-check", tags=["fact-check"])


# ── Internal service function (called by other routers without HTTP overhead) ──

def process_fact_check(request: FactCheckRequest) -> FactCheckResponse | None:
    """
    Public entry-point for the Fact-Check Engine.

    Accepts a FactCheckRequest, runs the LangGraph pipeline, and returns a
    FactCheckResponse.  Returns None if the claim is empty or the pipeline
    produces no result — callers decide whether to surface that as an error.

    This function is SYNCHRONOUS and must be run via asyncio.to_thread() from
    any async caller (live_audit, interactive, etc.).
    """
    claim = (request.claim or "").strip()
    if not claim:
        logger.warning("process_fact_check called with empty claim")
        return None

    logger.info(
        "Fact-check requested — source=%r claim=%r…",
        request.source_type,
        claim[:80],
    )

    raw: dict | None = run_pipeline_from_claim(claim)

    if raw is None:
        logger.info("Pipeline returned None for claim %r", claim[:80])
        return None

    response = FactCheckResponse(
        id=raw["id"],
        claim_text=raw["claimText"],
        claim_veracity=raw["claimVeracity"],
        confidence_score=raw["confidenceScore"],
        summary_and_explanation=raw["summaryAndExplanation"],
        key_source=raw.get("keySource"),
        key_sources=raw.get("key_sources", []),
    )
    logger.info(
        "Fact-check complete — verdict=%s confidence=%.2f",
        response.claim_veracity,
        response.confidence_score,
    )
    return response


# ── HTTP endpoint (reachable by Scanner, Radar, external tooling) ─────────────

@router.post("", response_model=FactCheckResponse)
async def fact_check_endpoint(request: FactCheckRequest):
    """
    Synchronous LangGraph pipeline wrapped in an async HTTP endpoint.
    Usage: POST /fact-check  { "claim": "...", "source_type": "scanner" }
    """
    import asyncio

    result = await asyncio.to_thread(process_fact_check, request)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail="No verifiable claim detected or pipeline returned no result.",
        )
    return result
