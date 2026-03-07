"""
Agent 2d — Trusted Database Worker

Uses DDGS site-search to find Snopes and PolitiFact articles.
Avoids their JS-rendered search pages which return no DOM content.
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

logger = logging.getLogger("dfacto.worker_trusted")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

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
    # Only scan the first 600 chars — verdict label appears near the top
    t = text[:600].lower()
    # Longer phrases first (more specific)
    for phrase in _FALSE_HINTS:
        if phrase in t:
            return "contradict"
    for phrase in _TRUE_HINTS:
        if phrase in t:
            return "support"
    return "neutral"


def _fetch_text(url: str) -> str:
    try:
        with httpx.Client(headers=_HEADERS, timeout=8, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception as exc:
        logger.debug("Fetch failed %s: %s", url, exc)
        return ""


def _ddg_site_search(claim: str, site: str) -> str | None:
    """Find the best matching article on a trusted site using DDG."""
    try:
        with DDGS() as d:
            hits = list(d.text(f'site:{site} {claim}', max_results=3))
        for h in hits:
            href = h.get("href", "")
            if site in href:
                return href
        return None
    except Exception as exc:
        logger.debug("DDG site search failed for %s: %s", site, exc)
        return None


def _check_source(claim: str, site: str, source_name: str) -> dict | None:
    """Find and scrape a trusted fact-check article."""
    url = _ddg_site_search(claim, site)
    if not url:
        logger.debug("%s: no result found via DDG", source_name)
        return None

    text = _fetch_text(url)
    if not text:
        logger.debug("%s: fetched empty page at %s", source_name, url)
        return None

    stance = _keyword_stance(text)
    excerpt = text[:200].replace("\n", " ").strip()
    logger.info("%s: url=%s stance=%s", source_name, url[:70], stance)
    return {
        "source": source_name,
        "stance": stance,
        "excerpt": f"{source_name.title()}: {excerpt[:120]}...",
        "url": url,
        "trust_weight": 1.5,
    }


def search_trusted_dbs(claim: str) -> list[dict]:
    """Query Snopes and PolitiFact via DDG site-search and return evidence."""
    if not claim:
        return []
    results = []
    snopes = _check_source(claim, "snopes.com", "snopes")
    if snopes:
        results.append(snopes)
    pf = _check_source(claim, "politifact.com", "politifact")
    if pf:
        results.append(pf)
    logger.info("Trusted DBs: %d items", len(results))
    return results
