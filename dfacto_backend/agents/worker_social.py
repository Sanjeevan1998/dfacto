"""
Agent 2c — Social & Forums Worker

Strategy:
  - Queries Reddit's public JSON API (no auth, no extra packages) for posts
    related to the claim.
  - Searches r/factcheck, r/skeptic, r/news, and r/worldnews.
  - Keyword stance detection on post titles + selftext excerpts.
  - Trust weight 0.6 (lower than authoritative sources — gauges public discourse).
  - Uses stdlib urllib only — no new dependencies.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("dfacto.worker_social")

_REDDIT_SUBREDDITS = ["factcheck", "skeptic", "news", "worldnews"]
_REDDIT_HEADERS = {"User-Agent": "dfacto-factchecker/1.0 (research tool)"}
_REQUEST_TIMEOUT = 6

_FALSE_HINTS = {
    "false", "debunked", "misinformation", "misleading", "hoax",
    "myth", "fake", "incorrect", "fabricated", "no evidence",
}
_TRUE_HINTS = {
    "true", "confirmed", "verified", "accurate", "correct",
    "real", "legit", "proven", "evidence shows",
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


def _reddit_search(claim: str, subreddit: str) -> list[dict]:
    """Search a subreddit for posts matching the claim via Reddit's JSON API."""
    encoded = urllib.parse.quote(claim)
    url = f"https://www.reddit.com/r/{subreddit}/search.json?q={encoded}&restrict_sr=1&sort=relevance&limit=3&t=year"
    try:
        req = urllib.request.Request(url, headers=_REDDIT_HEADERS)
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        posts = data.get("data", {}).get("children", [])
        return [p["data"] for p in posts if p.get("kind") == "t3"]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
        logger.debug("Reddit search failed for r/%s: %s", subreddit, exc)
        return []


def search_social(claim: str) -> list[dict]:
    """
    Query Reddit subreddits for public discourse on the claim.
    Returns up to 3 evidence items representing social signal.
    """
    if not claim:
        return []

    seen_urls: set[str] = set()
    results: list[dict] = []

    for subreddit in _REDDIT_SUBREDDITS:
        if len(results) >= 3:
            break

        posts = _reddit_search(claim, subreddit)
        for post in posts:
            if len(results) >= 3:
                break

            url = post.get("url", "")
            permalink = f"https://reddit.com{post.get('permalink', '')}"
            title = post.get("title", "")
            selftext = post.get("selftext", "")
            combined = f"{title} {selftext}"

            if not title or permalink in seen_urls:
                continue

            seen_urls.add(permalink)
            stance = _keyword_stance(combined)
            excerpt = f"r/{subreddit}: {title[:160]}"

            result = {
                "source": f"reddit/{subreddit}",
                "stance": stance,
                "excerpt": excerpt,
                "url": permalink,
                "trust_weight": 0.6,
            }
            results.append(result)
            logger.debug("social evidence: stance=%s subreddit=%s", stance, subreddit)

    logger.info("Social worker (Reddit): %d items", len(results))
    return results
