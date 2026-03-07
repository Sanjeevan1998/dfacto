"""
Agent 2d — Trusted Database Worker

Cross-references Snopes and PolitiFact for the given claim.
Returns verdict labels and source URLs from each.
"""

from __future__ import annotations

import logging
import urllib.parse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("dfacto.worker_trusted")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

_VERDICT_MAP = {
    # Snopes
    "true": "support",
    "false": "contradict",
    "mostly true": "support",
    "mostly false": "contradict",
    "mixture": "neutral",
    "unproven": "neutral",
    "outdated": "neutral",
    "miscaptioned": "contradict",
    # PolitiFact
    "pants on fire": "contradict",
    "half-true": "neutral",
    "mostly true": "support",
    "true": "support",
    "false": "contradict",
}


def _query_snopes(claim: str) -> dict | None:
    query = urllib.parse.quote_plus(claim)
    url = f"https://www.snopes.com/?s={query}"
    try:
        with httpx.Client(headers=_HEADERS, timeout=6, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # First result article
        article = soup.select_one("article.media-module")
        if not article:
            return None
        rating_tag = article.select_one(".rating-label")
        link_tag = article.select_one("a[href]")
        if not link_tag:
            return None
        result_url = link_tag["href"]
        verdict_raw = rating_tag.get_text(strip=True).lower() if rating_tag else "unproven"
        stance = _VERDICT_MAP.get(verdict_raw, "neutral")
        return {
            "source": "snopes",
            "stance": stance,
            "excerpt": f"Snopes verdict: {verdict_raw.title()}",
            "url": result_url,
            "trust_weight": 1.5,
        }
    except Exception as exc:
        logger.debug("Snopes query failed: %s", exc)
        return None


def _query_politifact(claim: str) -> dict | None:
    query = urllib.parse.quote_plus(claim)
    url = f"https://www.politifact.com/search/?q={query}"
    try:
        with httpx.Client(headers=_HEADERS, timeout=6, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # First result
        item = soup.select_one(".m-statement__body")
        link_tag = soup.select_one("article.m-statement a[href]")
        meter = soup.select_one(".m-statement__meter img")
        if not link_tag:
            return None
        result_url = "https://www.politifact.com" + link_tag["href"]
        verdict_raw = meter["alt"].lower() if meter and meter.get("alt") else "unknown"
        stance = _VERDICT_MAP.get(verdict_raw, "neutral")
        return {
            "source": "politifact",
            "stance": stance,
            "excerpt": f"PolitiFact rating: {verdict_raw.title()}",
            "url": result_url,
            "trust_weight": 1.5,
        }
    except Exception as exc:
        logger.debug("PolitiFact query failed: %s", exc)
        return None


def search_trusted_dbs(claim: str) -> list[dict]:
    """
    Query Snopes and PolitiFact and return available evidence items.
    Always returns a list (may be empty if both sources fail).
    """
    results = []
    snopes = _query_snopes(claim)
    if snopes:
        results.append(snopes)
    politifact = _query_politifact(claim)
    if politifact:
        results.append(politifact)
    return results
