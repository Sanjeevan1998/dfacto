"""
Agent 2d — Trusted Database Worker

Strategy:
  - TavilySearchResults with include_domains restricts search to Snopes,
    PolitiFact, and FactCheck.org — authoritative fact-checking sources.
  - Tavily returns clean LLM-ready text — no httpx or BeautifulSoup needed.
  - Keyword stance detection determines support/contradict/neutral.
  - Trust weight 1.5 (higher than general web) due to source authority.
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
load_dotenv()

from langchain_tavily import TavilySearch

logger = logging.getLogger("dfacto.worker_trusted")

_TRUSTED_DOMAINS = ["snopes.com", "politifact.com", "factcheck.org"]

_FALSE_HINTS = [
    "pants on fire", "mostly false", "no evidence", "debunked",
    "misinformation", "misleading", "fabricated", "fake", "false",
    "incorrect", "myth",
]
_TRUE_HINTS = [
    "mostly true", "half true", "verified", "confirmed", "accurate",
    "correct", "real", "true",
]


def _keyword_stance(text: str) -> str:
    t = text[:800].lower()
    for phrase in _FALSE_HINTS:
        if phrase in t:
            return "contradict"
    for phrase in _TRUE_HINTS:
        if phrase in t:
            return "support"
    return "neutral"


def _get_tavily_tool(max_results: int = 3) -> TavilySearch:
    return TavilySearch(
        max_results=max_results,
        search_depth="advanced",
        include_domains=_TRUSTED_DOMAINS,
        include_answer=True,
        include_raw_content=False,
    )


def search_trusted_dbs(claim: str) -> list[dict]:
    """
    Query Snopes, PolitiFact, and FactCheck.org via Tavily.
    Tavily restricts results to those domains — no secondary HTTP requests.
    """
    if not claim:
        return []

    try:
        tool = _get_tavily_tool()
        response = tool.invoke({"query": claim})
        # TavilySearch returns a dict with a 'results' list
        if isinstance(response, dict):
            raw_results = response.get("results", [])
        else:
            raw_results = []
    except Exception as exc:
        logger.warning("Tavily trusted-DB search failed: %s", exc)
        return []

    if not raw_results:
        logger.info("Tavily trusted-DB: no results found")
        return []

    results = []
    for item in raw_results:
        url = item.get("url", "")
        content = item.get("content", "").strip()
        if not content:
            continue

        # Identify which trusted source this came from
        source_name = next(
            (d.replace(".com", "").replace(".org", "") for d in _TRUSTED_DOMAINS if d in url),
            "trusted",
        )
        stance = _keyword_stance(content)
        excerpt = f"{source_name.title()}: {content[:160].replace(chr(10), ' ').strip()}..."

        result = {
            "source": source_name,
            "stance": stance,
            "excerpt": excerpt,
            "url": url,
            "trust_weight": 1.5,
        }
        results.append(result)
        logger.info("trusted evidence: source=%s stance=%s url=%s", source_name, stance, url[:70])

    logger.info("Trusted DBs (Tavily): %d items", len(results))
    return results
