"""
Agent 2e — News Article Worker

Strategy:
  - Queries two complementary news APIs in parallel:
      1. GNews.io (/api/v4/search)   — broad global news, full article content
      2. NewsData.io (/api/1/news)   — real-time news with source diversity
  - Returns up to 6 recent news articles (3 per source) with stance detection.
  - Complements Tavily web/trusted searches with structured news data.
  - Trust weight 1.0 (real news, but not dedicated fact-checkers).
  - Uses stdlib urllib + concurrent.futures — no new dependencies.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("dfacto.worker_news")

_REQUEST_TIMEOUT = 8

_FALSE_HINTS = {
    "false", "debunked", "misinformation", "misleading", "hoax",
    "myth", "fake", "incorrect", "fabricated", "no evidence", "disproved",
}
_TRUE_HINTS = {
    "true", "confirmed", "verified", "accurate", "correct",
    "real", "legit", "proven", "evidence shows", "reports confirm",
}


def _keyword_stance(text: str) -> str:
    t = text.lower()
    false_score = sum(1 for kw in _FALSE_HINTS if kw in t)
    true_score = sum(1 for kw in _TRUE_HINTS if kw in t)
    if false_score > true_score:
        return "contradict"
    if true_score > false_score:
        return "support"
    return "neutral"


def _fetch_gnews(q: str, max_results: int = 3) -> list[dict]:
    """Query GNews.io /api/v4/search."""
    api_key = os.getenv("GNEWS_API_KEY", "")
    if not api_key:
        return []

    params = urllib.parse.urlencode({
        "q": q,
        "apikey": api_key,
        "lang": "en",
        "max": max_results,
    })
    url = f"https://gnews.io/api/v4/search?{params}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "dfacto-factchecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.debug("GNews.io request failed: %s", exc)
        return []

    results = []
    for article in data.get("articles", [])[:max_results]:
        url_ = article.get("url", "")
        if not url_:
            continue
        title = article.get("title", "")
        description = article.get("description", "") or ""
        source_name = article.get("source", {}).get("name", "GNews")
        published_at = (article.get("publishedAt", "") or "")[:10]
        combined = f"{title} {description}"
        results.append({
            "source": f"news/{source_name.lower().replace(' ', '_')}",
            "stance": _keyword_stance(combined),
            "excerpt": f"[{source_name}, {published_at}] {title}: {description[:120]}",
            "url": url_,
            "trust_weight": 1.0,
        })
    return results


def _fetch_newsdataio(q: str, max_results: int = 3) -> list[dict]:
    """Query NewsData.io /api/1/news."""
    api_key = os.getenv("NEWS_DATA_IO_API_KEY", "")
    if not api_key:
        return []

    params = urllib.parse.urlencode({
        "q": q,
        "apikey": api_key,
        "language": "en",
        "size": max_results,
    })
    url = f"https://newsdata.io/api/1/news?{params}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "dfacto-factchecker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        logger.debug("NewsData.io request failed: %s", exc)
        return []

    if data.get("status") != "success":
        logger.debug("NewsData.io error: %s", data.get("message", ""))
        return []

    results = []
    for article in (data.get("results") or [])[:max_results]:
        url_ = article.get("link", "")
        if not url_:
            continue
        title = article.get("title", "")
        description = article.get("description", "") or ""
        source_name = article.get("source_name", "NewsData")
        published_at = (article.get("pubDate", "") or "")[:10]
        combined = f"{title} {description}"
        results.append({
            "source": f"news/{source_name.lower().replace(' ', '_')}",
            "stance": _keyword_stance(combined),
            "excerpt": f"[{source_name}, {published_at}] {title}: {description[:120]}",
            "url": url_,
            "trust_weight": 1.0,
        })
    return results


def search_news(claim: str, search_query: str = "") -> list[dict]:
    """
    Query GNews.io and NewsData.io in parallel for recent news about the claim.
    search_query: pre-compressed query from node_categorize; falls back to claim truncation.
    Returns up to 6 deduplicated evidence items.
    """
    if not claim:
        return []

    q = (search_query.strip() or claim[:100])

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(_fetch_gnews, q)
        f2 = ex.submit(_fetch_newsdataio, q)
        gnews_results = f1.result()
        newsdata_results = f2.result()

    # Deduplicate by URL
    seen_urls: set[str] = set()
    combined: list[dict] = []
    for item in gnews_results + newsdata_results:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            combined.append(item)
            logger.debug("news evidence: stance=%s source=%s", item["stance"], item["source"])

    logger.info(
        "News worker: %d GNews + %d NewsData = %d unique items for query %r",
        len(gnews_results), len(newsdata_results), len(combined), q[:60],
    )
    return combined[:6]
