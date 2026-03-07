"""
Agent 2a — Advanced AI Web Search Worker

Strategy:
  - TavilySearchResults (LangChain-community) fetches clean, LLM-ready text
    directly from the web — no httpx, no BeautifulSoup HTML parsing.
  - Gemini 2.0 Flash classifies the stance of each Tavily result.
  - Returns evidence items with trust_weight based on source reputation.
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

logger = logging.getLogger("dfacto.worker_web")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


def _get_tavily_tool(max_results: int = 5) -> TavilySearch:
    return TavilySearch(
        max_results=max_results,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=False,
    )


_STANCE_PROMPT = """\
You are a fact-checking assistant. Claim: "{claim}"

Article content (from Tavily search):
{content}

Does this content SUPPORT, CONTRADICT, or is it NEUTRAL about the claim?
Return ONLY valid JSON (no markdown fences):
{{"stance": "<support|contradict|neutral>", "excerpt": "<1-2 sentence key finding>"}}
"""

_FALSE_HINTS = {"false", "debunked", "myth", "misinformation", "incorrect", "pants on fire",
                "mostly false", "fake", "misleading", "no evidence"}
_TRUE_HINTS = {"true", "confirmed", "correct", "verified", "accurate", "mostly true", "real"}


def _keyword_stance(claim: str, url: str, content: str, trust_weight: float, source: str) -> dict:
    t = content.lower()
    false_score = sum(1 for kw in _FALSE_HINTS if kw in t)
    true_score = sum(1 for kw in _TRUE_HINTS if kw in t)
    if false_score > true_score:
        stance = "contradict"
    elif true_score > false_score:
        stance = "support"
    else:
        stance = "neutral"
    excerpt = content[:200].replace("\n", " ").strip()
    return {"source": source, "stance": stance, "excerpt": excerpt, "url": url, "trust_weight": trust_weight}


def _classify_stance(claim: str, url: str, content: str, trust_weight: float, source: str) -> dict:
    try:
        prompt = _STANCE_PROMPT.format(claim=claim, content=content[:2000])
        resp = _get_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=150),
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
        parsed = json.loads(raw)
        return {
            "source": source,
            "stance": parsed.get("stance", "neutral"),
            "excerpt": parsed.get("excerpt", content[:120]),
            "url": url,
            "trust_weight": trust_weight,
        }
    except Exception as exc:
        logger.debug("Gemini stance failed for %s, using keyword scan: %s", url, exc)
        return _keyword_stance(claim, url, content, trust_weight, source)


def search_web(claim: str, max_results: int = 5) -> list[dict]:
    """
    Fetch fact-check evidence for the claim using Tavily.
    Tavily returns pre-cleaned LLM-ready text — no secondary HTTP requests needed.
    """
    if not claim or not claim.strip():
        return []

    try:
        tool = _get_tavily_tool(max_results=max_results)
        response = tool.invoke({"query": f'fact check "{claim}"'})
        # TavilySearch returns a dict with a 'results' list
        if isinstance(response, dict):
            raw_results = response.get("results", [])
        else:
            raw_results = []
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return []

    if not raw_results:
        logger.info("Tavily returned no results for claim")
        return []

    results = []
    for item in raw_results:
        url = item.get("url", "")
        content = item.get("content", "").strip()
        if not content:
            continue
        evidence = _classify_stance(claim, url, content, trust_weight=1.0, source="web")
        results.append(evidence)
        logger.debug("web evidence: stance=%s url=%s", evidence["stance"], url[:70])

    logger.info("Web worker (Tavily): %d items", len(results))
    return results
