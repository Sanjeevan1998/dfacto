"""
Agent 2b — Multimodal Analysis Worker

Strategy:
  - Uses Tavily to fetch broader article context about the claim.
  - Passes the combined content to Gemini 2.0 Flash for deep semantic analysis:
    contextual nuance, historical precedent, scientific consensus signals.
  - Supplements Agents 2a/2d with a higher-reasoning pass over the evidence.
  - Trust weight 1.2 — between general web and authoritative fact-checkers.
"""

from __future__ import annotations

import json
import logging
import os
import re

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types as genai_types
from langchain_tavily import TavilySearch

logger = logging.getLogger("dfacto.worker_multimodal")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


_ANALYSIS_PROMPT = """\
You are a senior fact-checker with expertise in scientific, historical, and political analysis.

Claim to evaluate: "{claim}"

Evidence gathered from multiple sources:
{evidence_block}

Based on this evidence, provide a comprehensive analysis. Respond ONLY with valid JSON (no markdown):
{{
  "stance": "<support|contradict|neutral>",
  "confidence": <0.0 to 1.0>,
  "key_finding": "<1-2 sentence synthesis of the most important evidence>",
  "nuance": "<any important caveats, context, or partial truths>"
}}
"""


def _build_evidence_block(tavily_results: list[dict]) -> str:
    parts = []
    for i, item in enumerate(tavily_results, 1):
        url = item.get("url", "")
        content = item.get("content", "")[:600]
        parts.append(f"[Source {i}] {url}\n{content}")
    return "\n\n".join(parts)


def analyze_multimodal(claim: str, search_query: str = "", max_results: int = 4) -> list[dict]:
    """
    Deep semantic analysis of claim using Tavily evidence + Gemini reasoning.
    Returns a single consolidated evidence item (the multimodal analysis).
    search_query: pre-compressed query from node_categorize; falls back to claim truncation.
    """
    if not claim:
        return []

    q = search_query.strip() or claim[:120]
    # Fetch broad context with Tavily
    try:
        tool = TavilySearch(
            max_results=max_results,
            search_depth="advanced",
            include_answer=True,
            include_raw_content=False,
        )
        response = tool.invoke({"query": f'analysis context {q}'})
        # TavilySearch returns a dict with a 'results' list
        tavily_results = response.get("results", []) if isinstance(response, dict) else []
    except Exception as exc:
        logger.warning("Tavily fetch failed in multimodal worker: %s", exc)
        return []

    if not tavily_results:
        return []

    evidence_block = _build_evidence_block(tavily_results)

    try:
        prompt = _ANALYSIS_PROMPT.format(claim=claim, evidence_block=evidence_block)
        resp = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=300,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = resp.text.strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1:
            raw = raw[s : e + 1]
        parsed = json.loads(raw)

        result = {
            "source": "multimodal_analysis",
            "stance": parsed.get("stance", "neutral"),
            "excerpt": parsed.get("key_finding", "")[:300],
            "url": tavily_results[0].get("url", "") if tavily_results else "",
            "trust_weight": 1.2,
            "nuance": parsed.get("nuance", ""),
            "confidence": float(parsed.get("confidence", 0.5)),
        }
        logger.info(
            "Multimodal analysis: stance=%s confidence=%.2f",
            result["stance"],
            result["confidence"],
        )
        return [result]

    except Exception as exc:
        logger.warning("Multimodal Gemini analysis failed: %s", exc)
        return []
