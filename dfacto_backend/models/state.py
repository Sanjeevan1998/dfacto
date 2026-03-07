"""
GraphState — the shared Pydantic model that flows through every
node in the LangGraph supervisor pipeline.
"""

from __future__ import annotations

from typing import Annotated, Any, Sequence
from pydantic import BaseModel, Field
import operator


class EvidenceItem(BaseModel):
    """A single piece of evidence returned by a worker agent."""

    source: str = Field(description="Origin: 'web', 'snopes', 'politifact', etc.")
    stance: str = Field(description="'support' | 'contradict' | 'neutral'")
    excerpt: str = Field(default="", description="Relevant snippet from the source")
    url: str = Field(default="", description="URL of the source page")
    trust_weight: float = Field(
        default=1.0,
        description="Trust multiplier: trusted DBs = 1.5, web = 1.0",
    )


class GraphState(BaseModel):
    """
    The complete state object passed between LangGraph nodes.
    Each field is populated progressively as the graph executes.
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    audio_chunk: bytes = Field(
        default=b"",
        description="Raw PCM audio buffer received from the Flutter WebSocket.",
    )

    # ── Agent 1: Extraction ───────────────────────────────────────────────────
    transcript: str = Field(
        default="",
        description="Full text transcription produced by Gemini.",
    )
    core_claim: str = Field(
        default="",
        description="Isolated factual claim sentence extracted from the transcript.",
    )

    # ── Supervisor: Routing ────────────────────────────────────────────────────
    category: str = Field(
        default="unknown",
        description="Claim category: political | scientific | economic | other",
    )

    # ── Recursion Control ─────────────────────────────────────────────────────
    depth: int = Field(
        default=0,
        description="Current recursion depth. Capped at MAX_RECURSION_DEPTH.",
    )

    # ── Worker Results ────────────────────────────────────────────────────────
    worker_results: list[EvidenceItem] = Field(
        default_factory=list,
        description="Aggregated evidence items from all worker agents.",
    )

    # ── Synthesis: Output ─────────────────────────────────────────────────────
    confidence: float = Field(
        default=0.0,
        description="Aggregated confidence score in [0, 1].",
    )
    verdict: str = Field(
        default="UNKNOWN",
        description="Final verdict: TRUE | FALSE | MIXED | UNKNOWN",
    )
    summary: str = Field(
        default="",
        description="Human-readable explanation of the verdict.",
    )
    source_url: str | None = Field(
        default=None,
        description="Primary source URL to display in the Flutter Fact-Check Card.",
    )
