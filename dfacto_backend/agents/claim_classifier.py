"""
Agent 0: Claim Classifier

Quickly determines whether a spoken phrase:
  - Contains a checkable factual claim  → proceed to fact-check
  - Is conversational filler            → skip
  - Is incomplete / needs more context  → buffer and wait for next phrase

Uses Gemini with a tight, structured prompt to return JSON fast (~200ms).
Falls back to keyword heuristics if Gemini fails.
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

logger = logging.getLogger("dfacto.claim_classifier")

# Lazy-initialised client — created on first use so dotenv is loaded first
_client: genai.Client | None = None

def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client

_SYSTEM_PROMPT = """You are a claim classifier for a real-time fact-checking system. Given a spoken phrase (and optionally the full prior session transcript for context), respond ONLY with a JSON object:
{
  "is_claim": <true if it contains a verifiable factual claim, false if it's opinion/filler/question/greeting>,
  "needs_context": <true if the phrase references something unclear EVEN WITH the prior context provided>,
  "extracted_claim": "<the core claim as a fully self-contained standalone declarative sentence, or empty string if not a claim>",
  "is_duplicate": <true if extracted_claim is semantically identical or a direct paraphrase of any claim in the recent_claims list, false otherwise>
}

Rules:
- Use the prior session context to resolve referential phrases like "that caused cancer" or "he said it happened".
- If the prior context resolves what 'that'/'it'/'he' refers to, set needs_context=false and write a fully resolved extracted_claim.
- extracted_claim must be understandable without any surrounding context — it must name subjects explicitly.
- CONSOLIDATION RULE: If the new phrase contains multiple statements that mean the same thing (e.g. "Vaccines cause autism" and "There is a proven link between shots and autism"), merge them into ONE single canonical extracted_claim. Never output more than one claim.
- FOCUS RULE: extracted_claim must be a single SHORT declarative sentence (target under 25 words, hard limit 40 words). If the text describes multiple distinct events (e.g. flooding in Michigan AND tornadoes in Oklahoma), extract only the single most specific and checkable fact — typically the one with a named subject, number, or location. Do NOT chain multiple events into one long run-on sentence.
- DUPLICATE RULE: Compare extracted_claim against the recent_claims list (if provided). Set is_duplicate=true if the new claim is semantically identical or a direct paraphrase of any recent claim — even if worded differently. Set is_duplicate=false if no recent_claims are provided or the claim is genuinely new.

Examples:
"The Earth is flat" → {"is_claim": true, "needs_context": false, "extracted_claim": "The Earth is flat", "is_duplicate": false}
"Vaccines cause autism" → {"is_claim": true, "needs_context": false, "extracted_claim": "Vaccines cause autism", "is_duplicate": false}
"That happened in 2020" (no prior context) → {"is_claim": false, "needs_context": true, "extracted_claim": "", "is_duplicate": false}
"Yeah that's interesting" → {"is_claim": false, "needs_context": false, "extracted_claim": "", "is_duplicate": false}
"So anyway" → {"is_claim": false, "needs_context": false, "extracted_claim": "", "is_duplicate": false}
"Neil Armstrong was the first to walk on the Moon in 1969" → {"is_claim": true, "needs_context": false, "extracted_claim": "Neil Armstrong was the first person to walk on the Moon in 1969", "is_duplicate": false}
"""

# Filler patterns for keyword fallback
_FILLER_PATTERNS = re.compile(
    r"^(um+|uh+|hmm+|ok|okay|yeah|yes|no|so|well|right|anyway|"
    r"like|you know|i mean|i think|i feel|basically|literally|"
    r"actually|hello|hi|hey|bye|thanks|thank you|please|sorry|"
    r"wait|hold on|and|but|or|because|so um|so uh)[\s.!?]*$",
    re.IGNORECASE,
)

_CONTEXT_PATTERNS = re.compile(
    r"\b(that|it|this|he|she|they|them|those|these|there|here)\b.{0,30}"
    r"\b(did|caused|said|made|happened|was|were|is|are|has|have)\b",
    re.IGNORECASE,
)


def classify_claim(
    text: str,
    full_context: str = "",
    recent_claims: list[str] | None = None,
) -> dict:
    """
    Args:
        text: The new spoken window to classify (words since last check).
        full_context: The full session transcript so far (all words spoken).
                      Passed to Gemini so referential phrases can be resolved.
        recent_claims: Up to 10 canonical claims already sent to the pipeline
                       this session. Gemini uses these to detect duplicates/
                       paraphrases within a single call — no extra API round-trip.

    Returns:
        {
          "is_claim": bool,
          "needs_context": bool,
          "extracted_claim": str,
          "is_duplicate": bool,
          "source": "gemini" | "heuristic"
        }
    """
    text = text.strip()
    if not text or len(text.split()) < 2:
        return {"is_claim": False, "needs_context": False, "extracted_claim": "", "is_duplicate": False, "source": "heuristic"}

    # Fast heuristic check for obvious filler
    if _FILLER_PATTERNS.match(text):
        return {"is_claim": False, "needs_context": False, "extracted_claim": "", "is_duplicate": False, "source": "heuristic"}

    try:
        client = _get_client()
        context_section = (
            f'\n\nPrior session context (use to resolve ambiguous references):\n"""{full_context}"""\n'
            if full_context.strip()
            else ""
        )
        recent_section = ""
        if recent_claims:
            numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(recent_claims))
            recent_section = f"\n\nRecent already-checked claims (use for is_duplicate check):\n{numbered}\n"
        prompt = f'{_SYSTEM_PROMPT}{context_section}{recent_section}\nNew phrase to classify: "{text}"'
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = response.text.strip()
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e != -1:
            raw = raw[s : e + 1]
        result = json.loads(raw)
        result.setdefault("is_duplicate", False)
        result["source"] = "gemini"
        logger.info(
            "classify_claim: is_claim=%s needs_context=%s is_duplicate=%s claim=%r",
            result.get("is_claim"),
            result.get("needs_context"),
            result.get("is_duplicate"),
            result.get("extracted_claim", "")[:60],
        )
        return result
    except Exception as exc:
        logger.warning("classify_claim fallback to heuristic: %s", exc)
        # Heuristic fallback: check for referential ambiguity
        needs_ctx = bool(_CONTEXT_PATTERNS.search(text))
        # Treat as claim if >= 4 words and no filler match
        is_claim = len(text.split()) >= 4 and not needs_ctx
        return {
            "is_claim": is_claim,
            "needs_context": needs_ctx,
            "extracted_claim": text if is_claim else "",
            "is_duplicate": False,  # heuristic path cannot detect semantic duplicates
            "source": "heuristic",
        }


_MULTI_CLAIM_PROMPT = """You are a claim extractor for a real-time fact-checking system.

Extract ALL distinct verifiable factual claims from the text below.
Respond ONLY with a JSON array — each element is an object with two keys:
  "claim": "<standalone declarative sentence, 10-30 words, fully self-contained>",
  "is_duplicate": <true if this claim is semantically identical or a direct paraphrase of any claim in the recent_claims list, false otherwise>

Rules:
- Extract EVERY distinct verifiable fact (named people, numbers, locations, events, statistics).
- Do NOT merge unrelated facts into one — keep them separate.
- Each claim must be understandable without surrounding context — name subjects explicitly.
- Resolve pronouns using the prior session context if provided.
- Keep each claim SHORT (10-30 words, hard limit 40 words).
- Conversational filler, opinions, questions, greetings → do not extract.
- If no verifiable claims exist, return an empty array: []

Examples of good extraction from "Seven tornadoes hit Texas. Two people, Jody Owens and her daughter Lexi, died when their car was swept away":
[
  {"claim": "Seven tornadoes struck Texas, Kansas, and Oklahoma.", "is_duplicate": false},
  {"claim": "Jody Owens and her teenage daughter Lexi were killed when their vehicle was swept off the road by a tornado.", "is_duplicate": false}
]
"""


def extract_all_claims(
    text: str,
    full_context: str = "",
    recent_claims: list[str] | None = None,
) -> list[dict]:
    """
    Extract ALL distinct verifiable claims from a completed topic block.

    Args:
        text: The completed topic block text.
        full_context: Full session transcript for referential resolution.
        recent_claims: Already-processed claims this session (for is_duplicate check).

    Returns:
        List of {"claim": str, "is_duplicate": bool} dicts.
        Empty list if no verifiable claims found or on error.
    """
    text = text.strip()
    if not text or len(text.split()) < 3:
        return []

    try:
        client = _get_client()
        context_section = (
            f'\n\nPrior session context:\n"""{full_context}"""\n'
            if full_context.strip()
            else ""
        )
        recent_section = ""
        if recent_claims:
            numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(recent_claims))
            recent_section = f"\n\nRecent already-checked claims (use for is_duplicate):\n{numbered}\n"

        prompt = (
            f"{_MULTI_CLAIM_PROMPT}"
            f"{context_section}{recent_section}"
            f'\n\nText to extract claims from:\n"""{text}"""'
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=400,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = response.text.strip()
        s, e = raw.find("["), raw.rfind("]")
        if s == -1 or e == -1:
            return []
        claims_list = json.loads(raw[s : e + 1])
        if not isinstance(claims_list, list):
            return []

        results = []
        for item in claims_list:
            claim_text = item.get("claim", "").strip()
            if claim_text:
                results.append({
                    "claim": claim_text,
                    "is_duplicate": bool(item.get("is_duplicate", False)),
                })
        logger.info(
            "extract_all_claims: %d claim(s) found, %d duplicate(s)",
            len(results),
            sum(1 for r in results if r["is_duplicate"]),
        )
        return results

    except Exception as exc:
        logger.warning("extract_all_claims failed, falling back to classify_claim: %s", exc)
        # Graceful fallback: use single-claim classifier
        single = classify_claim(text, full_context, recent_claims)
        if single.get("is_claim") and not single.get("needs_context") and single.get("extracted_claim"):
            return [{"claim": single["extracted_claim"], "is_duplicate": single.get("is_duplicate", False)}]
        return []
