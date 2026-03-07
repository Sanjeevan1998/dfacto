"""
Agent 2a — Web / News Worker

Searches the web for evidence related to a factual claim.
Returns up to 3 stance-labelled evidence items.
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from bs4 import BeautifulSoup
from googlesearch import search
from google import genai
from google.genai import types

logger = logging.getLogger("dfacto.worker_web")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client


_STANCE_PROMPT = """
You are a fact-checking assistant. Given the claim and a web page excerpt, determine the stance.

Claim: {claim}

Page text (first 1500 chars):
{page_text}

Return ONLY valid JSON (no markdown):
{{
  "stance": "<support | contradict | neutral>",
  "excerpt": "<1-2 sentence relevant snippet from the page>"
}}
"""

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def _fetch_text(url: str, timeout: int = 5) -> str:
    """Fetch page and return plain text, or empty string on failure."""
    try:
        with httpx.Client(headers=_HEADERS, timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove script/style noise
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:2000]
    except Exception as exc:
        logger.debug("Web fetch failed for %s: %s", url, exc)
        return ""


def _classify_stance(claim: str, url: str, page_text: str) -> dict:
    """Ask Gemini to classify the stance of page_text relative to claim."""
    try:
        prompt = _STANCE_PROMPT.format(claim=claim, page_text=page_text[:1500])
        resp = _get_client().models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt],
        )
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        return {
            "source": "web",
            "stance": parsed.get("stance", "neutral"),
            "excerpt": parsed.get("excerpt", ""),
            "url": url,
            "trust_weight": 1.0,
        }
    except Exception as exc:
        logger.debug("Stance classification failed for %s: %s", url, exc)
        return {"source": "web", "stance": "neutral", "excerpt": "", "url": url, "trust_weight": 1.0}


def search_web(claim: str, max_results: int = 3) -> list[dict]:
    """
    Search the web for the given claim and return evidence items.
    Returns at most `max_results` items.
    """
    if not claim:
        return []

    results = []
    try:
        urls = list(search(f'fact check "{claim}"', num_results=5))
    except Exception as exc:
        logger.warning("Google search failed: %s", exc)
        return []

    for url in urls:
        if len(results) >= max_results:
            break
        page_text = _fetch_text(url)
        if not page_text:
            continue
        evidence = _classify_stance(claim, url, page_text)
        results.append(evidence)
        logger.debug("Web evidence: stance=%s url=%s", evidence["stance"], url)

    return results
