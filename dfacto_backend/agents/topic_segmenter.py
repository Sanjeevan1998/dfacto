"""
Agent 1b — Topic Segmenter

Analyzes a ~200-word spoken transcript chunk and identifies distinct topic blocks.
Each block is labeled COMPLETED or ONGOING so the buffer routing layer knows
whether to pass it downstream (fact-check) or carry it forward (next cycle).

Public API
----------
    segment_topics(chunk: str, session_context: str = "") -> list[TopicBlock]

Uses Gemini 2.0 Flash with a structured JSON prompt.
Falls back to a single COMPLETED block if the LLM fails — zero crash guarantee.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger("dfacto.topic_segmenter")

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class TopicBlock:
    topic_label: str          # 2-4 word human-readable label
    text: str                 # Verbatim spoken text for this topic block
    status: Literal["COMPLETED", "ONGOING"]

    @property
    def is_completed(self) -> bool:
        return self.status == "COMPLETED"

    @property
    def word_count(self) -> int:
        return len(self.text.split())


# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a real-time topic segmenter for a live broadcast fact-checking system.

You will receive a ~200-word spoken transcript chunk (verbatim, unedited, may \
include false starts and filler words).

Optionally you may also receive the full prior session context to help you \
understand ongoing topics.

Your job: identify all distinct topic blocks in the chunk.

Return ONLY a valid JSON array. Each element must be:
{
  "topic_label": "<2-4 word description of what this block is about>",
  "text": "<the exact verbatim text from the chunk that belongs to this topic>",
  "status": "COMPLETED" or "ONGOING"
}

DEFINITIONS:
- COMPLETED: The speaker has clearly finished this topic — they've reached a \
natural conclusion, moved on, or shifted focus. This block should be \
fact-checked independently.
- ONGOING: The speaker is still mid-thought on this topic at the point the \
chunk ends. The text should be carried forward into the next buffer cycle.

RULES:
1. The concatenation of all "text" fields must equal (or closely approximate) \
the original chunk — do not drop words.
2. Return 1 to 5 topic blocks maximum. If the entire chunk is one topic, \
return a single-element array.
3. Only the LAST block in the array can be ONGOING (a speaker can't be \
mid-thought on an earlier topic if they've already moved on).
4. Do not add commentary, markdown, or code fences — raw JSON array only.
"""


# ── Core function ───────────────────────────────────────────────────────────────

def segment_topics(chunk: str, session_context: str = "") -> list[TopicBlock]:
    """
    Segment a transcript chunk into topic blocks using Gemini 2.0 Flash.

    Args:
        chunk:           The ~200-word buffer to segment (isFinal words only).
        session_context: Full session transcript so far (for reference resolution).

    Returns:
        Ordered list of TopicBlock objects. At most one block is ONGOING, and
        it will always be the last element of the list.

    Fallback:
        If Gemini fails for any reason, returns [TopicBlock("unknown", chunk, "COMPLETED")]
        so the fact-check pipeline continues uninterrupted.
    """
    chunk = chunk.strip()
    if not chunk:
        return []

    context_section = (
        f'\n\nFull prior session context (for reference resolution):\n"""{session_context}"""\n'
        if session_context.strip()
        else ""
    )

    prompt = (
        f"{_SYSTEM_PROMPT}"
        f"{context_section}"
        f"\nTranscript chunk to segment:\n\"\"\"{chunk}\"\"\""
    )

    try:
        resp = _get_client().models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=600,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = resp.text.strip()

        # Extract JSON array from response (handle any wrapping prose)
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON array found in response: {raw[:200]}")
        parsed = json.loads(raw[start : end + 1])

        blocks = _validate_and_build(parsed, chunk)
        logger.info(
            "Topic segmenter: %d block(s) — COMPLETED: %d, ONGOING: %d",
            len(blocks),
            sum(1 for b in blocks if b.is_completed),
            sum(1 for b in blocks if not b.is_completed),
        )
        for b in blocks:
            logger.debug(
                "  [%s] %r — %d words — %r…",
                b.status, b.topic_label, b.word_count, b.text[:60],
            )
        return blocks

    except Exception as exc:
        logger.warning(
            "segment_topics fallback (entire chunk → COMPLETED): %s", exc
        )
        return [TopicBlock(topic_label="unknown", text=chunk, status="COMPLETED")]


# ── Validation ─────────────────────────────────────────────────────────────────

def _validate_and_build(parsed: list, original_chunk: str) -> list[TopicBlock]:
    """
    Parse and validate the raw JSON list from Gemini.

    Enforces:
    - Each element has topic_label, text, status fields
    - status is COMPLETED or ONGOING
    - Only the last element may be ONGOING
    - Non-empty text blocks only
    """
    blocks: list[TopicBlock] = []

    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        label = str(item.get("topic_label", "unknown")).strip() or "unknown"
        raw_status = str(item.get("status", "COMPLETED")).upper().strip()
        status: Literal["COMPLETED", "ONGOING"] = (
            "ONGOING" if raw_status == "ONGOING" else "COMPLETED"
        )
        # Enforce: only the last block can be ONGOING
        if status == "ONGOING" and i < len(parsed) - 1:
            status = "COMPLETED"
        blocks.append(TopicBlock(topic_label=label, text=text, status=status))

    if not blocks:
        # Gemini returned empty array — fall back to treating entire chunk as done
        return [TopicBlock(topic_label="unknown", text=original_chunk, status="COMPLETED")]

    return blocks
