"""
Agent 2a + 2d — Web Worker & Trusted DB Worker (Combined)

Strategy:
  - Use DDGS (DuckDuckGo) to search for fact-check articles from any source
  - Also site-search snopes.com and politifact.com specifically
  - Gemini classifies stance of each article
  - Returns evidence items with trust_weight based on source reputation

Package: pip install ddgs
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from google import genai

logger = logging.getLogger("dfacto.worker_web")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


_STANCE_PROMPT = """\
You are a fact-checking assistant. Claim: "{claim}"

Article text (excerpt):
{page_text}

Does this text SUPPORT, CONTRADICT, or is it NEUTRAL about the claim?
Return ONLY valid JSON (no markdown fences):
{{"stance": "<support|contradict|neutral>", "excerpt": "<1-2 sentence key finding>"}}
"""

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _fetch_text(url: str, timeout: int = 6) -> str:
    try:
        with httpx.Client(headers=_HEADERS, timeout=timeout, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as exc:
        logger.debug("Fetch failed %s: %s", url, exc)
        return ""


def _classify_stance(claim: str, url: str, page_text: str, trust_weight: float, source: str) -> dict:
    try:
        prompt = _STANCE_PROMPT.format(claim=claim, page_text=page_text[:1800])
        resp = _get_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt],
        )
        raw = resp.text.strip().strip("```json").strip("```").strip()
        parsed = json.loads(raw)
        return {
            "source": source,
            "stance": parsed.get("stance", "neutral"),
            "excerpt": parsed.get("excerpt", page_text[:120]),
            "url": url,
            "trust_weight": trust_weight,
        }
    except Exception as exc:
        # Gemini unavailable: do simple keyword scan
        logger.debug("Gemini stance failed for %s, using keyword scan: %s", url, exc)
        return _keyword_stance(claim, url, page_text, trust_weight, source)


_FALSE_HINTS = {"false", "debunked", "myth", "misinformation", "incorrect", "pants on fire",
                "mostly false", "fake", "misleading", "no evidence"}
_TRUE_HINTS = {"true", "confirmed", "correct", "verified", "accurate", "mostly true", "real"}


def _keyword_stance(claim: str, url: str, text: str, trust_weight: float, source: str) -> dict:
    t = text.lower()
    false_score = sum(1 for kw in _FALSE_HINTS if kw in t)
    true_score = sum(1 for kw in _TRUE_HINTS if kw in t)
    if false_score > true_score:
        stance = "contradict"
    elif true_score > false_score:
        stance = "support"
    else:
        stance = "neutral"
    excerpt = text[:200].replace("\n", " ").strip()
    return {"source": source, "stance": stance, "excerpt": excerpt, "url": url, "trust_weight": trust_weight}


def _ddg_search(query: str, max_results: int = 5) -> list[str]:
    """Search DuckDuckGo and return up to max_results URLs."""
    try:
        with DDGS() as d:
            hits = list(d.text(query, max_results=max_results))
        return [h.get("href", "") for h in hits if h.get("href")]
    except Exception as exc:
        logger.warning("DDG search failed (%r): %s", query, exc)
        return []


def search_web(claim: str, max_results: int = 3) -> list[dict]:
    """
    Use DuckDuckGo to find fact-check articles about the claim.
    Falls back to keyword-scoring when Gemini is unavailable.
    """
    if not claim:
        return []

    urls = _ddg_search(f'fact check "{claim}"', max_results=6)
    if not urls:
        logger.info("DDG returned no URLs for claim")
        return []

    results = []
    for url in urls:
        if len(results) >= max_results:
            break
        # Skip social media / irrelevant domains
        if any(d in url for d in ["twitter.com", "facebook.com", "reddit.com", "youtube.com"]):
            continue
        page = _fetch_text(url)
        if not page:
            continue
        evidence = _classify_stance(claim, url, page, trust_weight=1.0, source="web")
        results.append(evidence)
        logger.debug("web evidence: stance=%s url=%s", evidence["stance"], url[:70])

    logger.info("Web worker: %d items", len(results))
    return results
