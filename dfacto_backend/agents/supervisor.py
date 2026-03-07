"""
Supervisor — LangGraph StateGraph

Nodes:
  extract        → Agent 1 (Gemini transcription + claim extraction)
  categorize     → keyword-based claim category
  fan_out        → Agents 2a/2b/2c/2d in parallel threads
  aggregate      → confidence scoring from worker evidence
  route          → conditional: recurse (depth < max AND confidence < threshold) or judge
  node_judge     → Agent 2e Final Judge (Gemini 6-category verdict critique)
  synthesize     → formats the final FactCheckResult JSON

Entry:  extract (audio pipeline) or categorize (text injection pipeline)
Exit:   synthesize
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import re
import uuid
from typing import Literal

from google import genai
from google.genai import types as genai_types
from langgraph.graph import StateGraph, END

from models.state import GraphState, EvidenceItem
from agents.agent1_extractor import extract_claim
from agents.worker_web import search_web
from agents.worker_trusted import search_trusted_dbs
from agents.worker_social import search_social
from agents.worker_multimodal import analyze_multimodal

logger = logging.getLogger("dfacto.supervisor")

MAX_DEPTH: int = int(os.getenv("MAX_RECURSION_DEPTH", "3"))
MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.70"))

_gemini_client: genai.Client | None = None


def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _gemini_client


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
        logger.info("No claim found — skipping workers.")
        return {"category": "none", "confidence": 0.0, "verdict": "UNKNOWN"}
    claim_lower = state.core_claim.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in claim_lower for kw in keywords):
            logger.info("Category: %s", category)
            return {"category": category}
    return {"category": "other"}


def node_fan_out(state: GraphState) -> dict:
    """Run Agents 2a, 2b, 2c, 2d in parallel threads."""
    claim = state.core_claim
    if not claim:
        return {"worker_results": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_web = executor.submit(search_web, claim)
        future_trusted = executor.submit(search_trusted_dbs, claim)
        future_social = executor.submit(search_social, claim)
        future_multimodal = executor.submit(analyze_multimodal, claim)

        web_results = future_web.result()
        trusted_results = future_trusted.result()
        social_results = future_social.result()
        multimodal_results = future_multimodal.result()

    all_results = web_results + trusted_results + social_results + multimodal_results
    logger.info(
        "fan_out: %d web + %d trusted + %d social + %d multimodal = %d total",
        len(web_results), len(trusted_results), len(social_results),
        len(multimodal_results), len(all_results),
    )
    return {"worker_results": [EvidenceItem(**r) for r in all_results]}


def node_aggregate(state: GraphState) -> dict:
    """
    Compute confidence score from worker results.

    Scoring:
        support    → +trust_weight
        contradict → -trust_weight
        neutral    → 0

    Normalise to [0, 1]. Map to coarse verdict (will be refined by node_judge).
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
        confidence = (raw_score / weight_total + 1) / 2

    # Coarse verdict (refined by node_judge)
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


_JUDGE_PROMPT = """\
You are Agent 2e — the Final Judge in a fact-checking system. Your job is to critically evaluate conflicting evidence and produce a precise verdict.

Claim: "{claim}"

Evidence from multiple independent workers (source, stance, excerpt, trust_weight):
{evidence_block}

Aggregate confidence score: {confidence:.2f} (0=fully false, 0.5=mixed, 1=fully true)

Based on ALL evidence, determine the most accurate verdict. Use these 6 categories ONLY:
- TRUE: The claim is factually correct and well-supported.
- MOSTLY TRUE: Mostly accurate but with minor inaccuracies or missing nuance.
- HALF TRUE: Partially accurate — contains a mix of true and false elements.
- MOSTLY FALSE: Mostly inaccurate, though contains a kernel of truth.
- FALSE: The claim is factually incorrect, debunked, or unsupported.
- UNVERIFIABLE: Insufficient evidence to make a determination.

Respond ONLY with valid JSON (no markdown):
{{
  "verdict": "<TRUE|MOSTLY TRUE|HALF TRUE|MOSTLY FALSE|FALSE|UNVERIFIABLE>",
  "confidence": <refined 0.0-1.0>,
  "explanation": "<2-3 sentence synthesis explaining the verdict with evidence>",
  "key_source": "<URL of the single most authoritative source cited>"
}}
"""


def _build_evidence_block(items: list[EvidenceItem]) -> str:
    parts = []
    for i, item in enumerate(items, 1):
        parts.append(
            f"[{i}] source={item.source} stance={item.stance} "
            f"trust={item.trust_weight:.1f}\n    {item.excerpt[:160]}\n    url={item.url}"
        )
    return "\n\n".join(parts)


def node_judge(state: GraphState) -> dict:
    """
    Agent 2e — Final Judge.
    Uses Gemini to critically evaluate all evidence and produce a 6-category verdict.
    Falls back to coarse aggregate verdict if Gemini fails.
    """
    items = state.worker_results
    if not items or not state.core_claim.strip():
        return {}  # No change — synthesize will use aggregate verdict

    evidence_block = _build_evidence_block(items)
    prompt = _JUDGE_PROMPT.format(
        claim=state.core_claim,
        evidence_block=evidence_block,
        confidence=state.confidence,
    )

    # Find best source URL from trusted items
    best_url = None
    for item in sorted(items, key=lambda x: x.trust_weight, reverse=True):
        if item.url:
            best_url = item.url
            break

    try:
        resp = _get_gemini_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=350,
            ),
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
        parsed = json.loads(raw)

        verdict = parsed.get("verdict", state.verdict).upper()
        confidence = float(parsed.get("confidence", state.confidence))
        explanation = parsed.get("explanation", "")
        key_source = parsed.get("key_source") or best_url

        logger.info(
            "Final Judge: verdict=%s confidence=%.2f",
            verdict,
            confidence,
        )
        return {
            "verdict": verdict,
            "confidence": confidence,
            "summary": explanation,
            "source_url": key_source,
        }

    except Exception as exc:
        logger.warning("Final Judge Gemini failed, using aggregate verdict: %s", exc)
        # Build fallback summary from evidence excerpts
        excerpts = [i.excerpt for i in items if i.excerpt]
        summary = excerpts[0] if excerpts else f"Verdict based on {len(items)} sources."
        return {"summary": summary, "source_url": best_url}


def node_increment_depth(state: GraphState) -> dict:
    """Increment recursion depth counter before looping back to fan_out."""
    new_depth = state.depth + 1
    logger.info("Recursing: depth %d → %d", state.depth, new_depth)
    return {"depth": new_depth}


def node_synthesize(state: GraphState) -> dict:
    """Format the final FactCheckResult payload for Flutter."""
    if not state.summary:
        # Fallback: build from evidence excerpts
        excerpts = [i.excerpt for i in state.worker_results if i.excerpt]
        summary = excerpts[0] if excerpts else f"Verdict based on {len(state.worker_results)} sources."
        return {"summary": summary}
    return {}


# ── Routing logic ──────────────────────────────────────────────────────────────

def route_after_aggregate(state: GraphState) -> Literal["increment_depth", "node_judge"]:
    """
    Route to recursion (via increment_depth → fan_out) or Final Judge.
    Short-circuits directly to judge if no claim.
    """
    if not state.core_claim.strip():
        return "node_judge"
    if state.confidence < MIN_CONFIDENCE and state.depth < MAX_DEPTH:
        return "increment_depth"
    return "node_judge"


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph(start_at_extract: bool = True) -> StateGraph:
    builder = StateGraph(GraphState)

    if start_at_extract:
        builder.add_node("extract", node_extract)
    builder.add_node("categorize", node_categorize)
    builder.add_node("fan_out", node_fan_out)
    builder.add_node("aggregate", node_aggregate)
    builder.add_node("increment_depth", node_increment_depth)
    builder.add_node("node_judge", node_judge)
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
        {"increment_depth": "increment_depth", "node_judge": "node_judge"},
    )
    builder.add_edge("increment_depth", "fan_out")
    builder.add_edge("node_judge", "synthesize")
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
    Used by live_audit.py and POST /debug/check for testing without a microphone.
    """
    if not claim_text.strip():
        return None
    logger.info("Claim injection — claim: %r", claim_text)
    initial_state = GraphState(
        audio_chunk=b"",
        transcript=claim_text,
        core_claim=claim_text,
    )
    final: dict = _claims_graph.invoke(initial_state)
    return _format_result(final)


# 6-category Flutter veracity map
_VERACITY_MAP = {
    "TRUE":          "trueVerdict",
    "MOSTLY TRUE":   "mostlyTrue",
    "HALF TRUE":     "halfTrue",
    "MOSTLY FALSE":  "mostlyFalse",
    "FALSE":         "falseVerdict",
    "UNVERIFIABLE":  "unknown",
    # Legacy fallbacks
    "MIXED":         "halfTrue",
    "UNKNOWN":       "unknown",
}


def _format_result(final: dict) -> dict | None:
    """Convert LangGraph output dict to Flutter FactCheckResult-compatible payload."""
    core_claim = final.get("core_claim", "")
    if not core_claim:
        logger.info("No claim detected — skipping result.")
        return None

    verdict = final.get("verdict", "UNKNOWN").upper()
    return {
        "id": str(uuid.uuid4()),
        "claimText": core_claim,
        "claimVeracity": _VERACITY_MAP.get(verdict, "unknown"),
        "confidenceScore": round(final.get("confidence", 0.0), 3),
        "summaryAndExplanation": final.get("summary", ""),
        "keySource": final.get("source_url"),
    }
