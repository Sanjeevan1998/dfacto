"""
Supervisor — LangGraph StateGraph

Nodes:
  extract     → calls Agent 1 (Gemini transcription + claim)
  categorize  → classifies the claim category
  fan_out     → runs Agent 2a (web) + Agent 2d (trusted DBs) in parallel
  aggregate   → scores confidence from worker evidence
  route       → conditional: recurse (depth < max AND confidence < threshold) or synthesize
  synthesize  → formats the final FactCheckResult JSON

Entry:  extract
Exit:   synthesize
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import uuid
from typing import Literal

from langgraph.graph import StateGraph, END

from models.state import GraphState, EvidenceItem
from agents.agent1_extractor import extract_claim
from agents.worker_web import search_web
from agents.worker_trusted import search_trusted_dbs

logger = logging.getLogger("dfacto.supervisor")

MAX_DEPTH: int = int(os.getenv("MAX_RECURSION_DEPTH", "3"))
MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.70"))

# ── Node functions ─────────────────────────────────────────────────────────────

def node_extract(state: GraphState) -> dict:
    """Agent 1 — transcribe audio and extract core claim."""
    result = extract_claim(state.audio_chunk)
    claim = result.get("core_claim", "")
    logger.info("Extracted claim: %r", claim if claim else "<none>")
    return {
        "transcript": result["transcript"],
        "core_claim": claim,
    }


_CATEGORY_KEYWORDS = {
    "political": ["government", "president", "senator", "congress", "election", "vote", "party", "policy"],
    "scientific": ["vaccine", "covid", "climate", "study", "research", "science", "dna", "evolution"],
    "economic": ["gdp", "economy", "inflation", "unemployment", "recession", "market", "trade", "tax"],
}


def node_categorize(state: GraphState) -> dict:
    """Keyword-based claim categorisation. Short-circuits if no claim found."""
    if not state.core_claim.strip():
        # No claim — mark as unknown and skip to synthesize via route
        logger.info("No claim found — skipping workers.")
        return {"category": "none", "confidence": 0.0, "verdict": "UNKNOWN"}
    claim_lower = state.core_claim.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in claim_lower for kw in keywords):
            logger.info("Category: %s", category)
            return {"category": category}
    return {"category": "other"}


def node_fan_out(state: GraphState) -> dict:
    """Run Agent 2a and Agent 2d in parallel threads."""
    claim = state.core_claim
    if not claim:
        return {"worker_results": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_web = executor.submit(search_web, claim)
        future_trusted = executor.submit(search_trusted_dbs, claim)
        web_results = future_web.result()
        trusted_results = future_trusted.result()

    all_results = web_results + trusted_results
    logger.info(
        "fan_out: %d web + %d trusted = %d total evidence items",
        len(web_results), len(trusted_results), len(all_results),
    )
    return {"worker_results": [EvidenceItem(**r) for r in all_results]}


def node_aggregate(state: GraphState) -> dict:
    """
    Compute confidence score from worker results.

    Scoring:
        support    → +trust_weight
        contradict → -trust_weight
        neutral    → 0

    Normalise to [0, 1]. Map to verdict.
    """
    items = state.worker_results
    if not items:
        return {"confidence": 0.0, "verdict": "UNKNOWN"}

    raw_score = 0.0
    weight_total = 0.0
    for item in items:
        w = item.trust_weight
        weight_total += w
        if item.stance == "support":
            raw_score += w
        elif item.stance == "contradict":
            raw_score -= w

    if weight_total == 0:
        confidence = 0.0
    else:
        # Normalise: raw is in [-weight_total, +weight_total] → [0, 1]
        confidence = (raw_score / weight_total + 1) / 2

    # Verdict mapping
    if confidence >= 0.70:
        verdict = "TRUE"
    elif confidence <= 0.30:
        verdict = "FALSE"
    elif 0.40 <= confidence < 0.70:
        verdict = "MIXED"
    else:
        verdict = "UNKNOWN"

    logger.info("Aggregate: confidence=%.3f verdict=%s depth=%d", confidence, verdict, state.depth)
    return {"confidence": confidence, "verdict": verdict}


def node_increment_depth(state: GraphState) -> dict:
    """Increment recursion depth counter before looping back to fan_out."""
    new_depth = state.depth + 1
    logger.info("Recursing: depth %d → %d", state.depth, new_depth)
    return {"depth": new_depth}


def node_synthesize(state: GraphState) -> dict:
    """Format the final FactCheckResult payload for Flutter."""
    # Pick best source URL (prefer trusted DBs)
    source_url = None
    for item in sorted(state.worker_results, key=lambda x: x.trust_weight, reverse=True):
        if item.url:
            source_url = item.url
            break

    # Build summary from top evidence excerpt
    excerpts = [i.excerpt for i in state.worker_results if i.excerpt]
    summary = excerpts[0] if excerpts else f"Verdict based on {len(state.worker_results)} sources."

    logger.info("Synthesized: verdict=%s confidence=%.3f", state.verdict, state.confidence)
    return {
        "summary": summary,
        "source_url": source_url,
    }


# ── Routing logic ──────────────────────────────────────────────────────────────

def route_after_aggregate(state: GraphState) -> Literal["increment_depth", "synthesize"]:
    """
    Route to recursion (via increment_depth node) or synthesis.
    Also short-circuits if there was no claim.
    """
    # Short-circuit: no claim, nothing to do
    if not state.core_claim.strip():
        return "synthesize"
    if state.confidence < MIN_CONFIDENCE and state.depth < MAX_DEPTH:
        return "increment_depth"
    return "synthesize"


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph(start_at_extract: bool = True) -> StateGraph:
    builder = StateGraph(GraphState)

    if start_at_extract:
        builder.add_node("extract", node_extract)
    builder.add_node("categorize", node_categorize)
    builder.add_node("fan_out", node_fan_out)
    builder.add_node("aggregate", node_aggregate)
    builder.add_node("increment_depth", node_increment_depth)
    builder.add_node("synthesize", node_synthesize)

    if start_at_extract:
        builder.set_entry_point("extract")
        builder.add_edge("extract", "categorize")
    else:
        builder.set_entry_point("categorize")

    builder.add_edge("categorize", "fan_out")
    builder.add_edge("fan_out", "aggregate")
    builder.add_conditional_edges(
        "aggregate",
        route_after_aggregate,
        {"increment_depth": "increment_depth", "synthesize": "synthesize"},
    )
    builder.add_edge("increment_depth", "fan_out")
    builder.add_edge("synthesize", END)

    return builder.compile()


# Full pipeline (audio → extract → categorize → … → synthesize)
_graph = _build_graph(start_at_extract=True)

# Text-injection pipeline (claim → categorize → … → synthesize), skips Gemini
_claims_graph = _build_graph(start_at_extract=False)


# ── Public API ─────────────────────────────────────────────────────────────────

def run_pipeline(audio_chunk: bytes) -> dict | None:
    """Run the full pipeline from raw PCM audio bytes."""
    initial_state = GraphState(audio_chunk=audio_chunk)
    final: dict = _graph.invoke(initial_state)
    return _format_result(final)


def run_pipeline_from_claim(claim_text: str) -> dict | None:
    """
    Bypass Gemini audio transcription and inject a plain-text claim directly.
    Used by POST /debug/check for testing without a microphone.
    """
    if not claim_text.strip():
        return None
    logger.info("Debug injection — claim: %r", claim_text)
    initial_state = GraphState(
        audio_chunk=b"",
        transcript=claim_text,
        core_claim=claim_text,
    )
    final: dict = _claims_graph.invoke(initial_state)
    return _format_result(final)


def _format_result(final: dict) -> dict | None:
    """Convert LangGraph output dict to Flutter FactCheckResult-compatible payload."""
    core_claim = final.get("core_claim", "")
    if not core_claim:
        logger.info("No claim detected — skipping result.")
        return None

    verdict = final.get("verdict", "UNKNOWN")
    veracity_map = {
        "TRUE": "trueVerdict",
        "FALSE": "falseVerdict",
        "MIXED": "mixed",
        "UNKNOWN": "unknown",
    }
    return {
        "id": str(uuid.uuid4()),
        "claimText": core_claim,
        "claimVeracity": veracity_map.get(verdict, "unknown"),
        "confidenceScore": round(final.get("confidence", 0.0), 3),
        "summaryAndExplanation": final.get("summary", ""),
        "keySource": final.get("source_url"),
    }
