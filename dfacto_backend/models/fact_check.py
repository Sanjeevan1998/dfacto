"""
Shared Pydantic schemas for the Fact-Check Microservice boundary.

Nothing in this file may import from routers/, WebSocket, or audio layers.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class FactCheckRequest(BaseModel):
    """Standard input to the Fact-Check Engine — source-agnostic."""
    claim: str = Field(..., description="Canonical, deduplicated claim text.")
    context: Optional[str] = Field(
        None,
        description="Optional surrounding transcript or page context for reference resolution.",
    )
    source_type: str = Field(
        "unspecified",
        description="Logical origin of the claim: 'live_audit' | 'interactive' | 'scanner' | 'debug'.",
    )


class FactCheckResponse(BaseModel):
    """Standard output of the Fact-Check Engine — UI-ready."""
    id: str
    claim_text: str
    claim_veracity: str           # trueVerdict | mostlyTrue | halfTrue | mostlyFalse | falseVerdict | unknown
    confidence_score: float
    summary_and_explanation: str
    key_source: Optional[str]     # single most-authoritative URL (backward compat)
    key_sources: list[str]        # top-3 URLs
