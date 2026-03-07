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
  "extracted_claim": "<the core claim as a fully self-contained standalone declarative sentence, or empty string if not a claim>"
}

Rules:
- Use the prior session context to resolve referential phrases like "that caused cancer" or "he said it happened".
- If the prior context resolves what 'that'/'it'/'he' refers to, set needs_context=false and write a fully resolved extracted_claim.
- extracted_claim must be understandable without any surrounding context — it must name subjects explicitly.

Examples:
"The Earth is flat" → {"is_claim": true, "needs_context": false, "extracted_claim": "The Earth is flat"}
"Vaccines cause autism" → {"is_claim": true, "needs_context": false, "extracted_claim": "Vaccines cause autism"}
"That happened in 2020" (no prior context) → {"is_claim": false, "needs_context": true, "extracted_claim": ""}
"Yeah that's interesting" → {"is_claim": false, "needs_context": false, "extracted_claim": ""}
"So anyway" → {"is_claim": false, "needs_context": false, "extracted_claim": ""}
"Neil Armstrong was the first to walk on the Moon in 1969" → {"is_claim": true, "needs_context": false, "extracted_claim": "Neil Armstrong was the first person to walk on the Moon in 1969"}
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


def classify_claim(text: str, full_context: str = "") -> dict:
    """
    Args:
        text: The new spoken window to classify (words since last check).
        full_context: The full session transcript so far (all words spoken).
                      Passed to Gemini so referential phrases can be resolved.

    Returns:
        {
          "is_claim": bool,
          "needs_context": bool,
          "extracted_claim": str,
          "source": "gemini" | "heuristic"
        }
    """
    text = text.strip()
    if not text or len(text.split()) < 2:
        return {"is_claim": False, "needs_context": False, "extracted_claim": "", "source": "heuristic"}

    # Fast heuristic check for obvious filler
    if _FILLER_PATTERNS.match(text):
        return {"is_claim": False, "needs_context": False, "extracted_claim": "", "source": "heuristic"}

    try:
        client = _get_client()
        context_section = (
            f'\n\nPrior session context (use to resolve ambiguous references):\n"""{full_context}"""\n'
            if full_context.strip()
            else ""
        )
        prompt = f'{_SYSTEM_PROMPT}{context_section}\nNew phrase to classify: "{text}"'
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=180,
            ),
        )
        raw = response.text.strip()
        # Strip any markdown code fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
        result = json.loads(raw)
        result["source"] = "gemini"
        logger.info(
            "classify_claim: is_claim=%s needs_context=%s claim=%r",
            result.get("is_claim"),
            result.get("needs_context"),
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
            "source": "heuristic",
        }
