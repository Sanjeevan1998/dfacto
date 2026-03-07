"""
Phase 2 Smoke Tests — dfacto_backend

Tests run WITHOUT a real Gemini API key by mocking the network calls.
Validates the full graph topology and routing logic deterministically.

Run: pytest tests/test_graph.py -v
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from models.state import GraphState, EvidenceItem


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_evidence(stance: str, source: str = "web", trust: float = 1.0) -> EvidenceItem:
    return EvidenceItem(
        source=source,
        stance=stance,
        excerpt=f"Test excerpt ({stance})",
        url=f"https://example.com/{stance}",
        trust_weight=trust,
    )


# ── Unit: GraphState ───────────────────────────────────────────────────────────

class TestGraphState:
    def test_default_values(self):
        state = GraphState()
        assert state.audio_chunk == b""
        assert state.transcript == ""
        assert state.core_claim == ""
        assert state.confidence == 0.0
        assert state.depth == 0
        assert state.verdict == "UNKNOWN"
        assert state.worker_results == []

    def test_custom_fields(self):
        state = GraphState(
            audio_chunk=b"\x00\x01",
            core_claim="The sky is green.",
            confidence=0.8,
            verdict="FALSE",
        )
        assert state.audio_chunk == b"\x00\x01"
        assert state.verdict == "FALSE"


# ── Unit: Confidence Scoring ───────────────────────────────────────────────────

class TestConfidenceScoring:
    def test_all_support_gives_high_confidence(self):
        from agents.supervisor import node_aggregate
        state = GraphState(
            core_claim="Test claim",
            worker_results=[
                _make_evidence("support"), _make_evidence("support"), _make_evidence("support"),
            ],
        )
        result = node_aggregate(state)
        assert result["confidence"] >= 0.70
        assert result["verdict"] == "TRUE"

    def test_all_contradict_gives_low_confidence(self):
        from agents.supervisor import node_aggregate
        state = GraphState(
            core_claim="Test claim",
            worker_results=[
                _make_evidence("contradict"), _make_evidence("contradict"),
            ],
        )
        result = node_aggregate(state)
        assert result["confidence"] <= 0.30
        assert result["verdict"] == "FALSE"

    def test_mixed_evidence_gives_mixed_verdict(self):
        from agents.supervisor import node_aggregate
        state = GraphState(
            core_claim="Test claim",
            worker_results=[
                _make_evidence("support"), _make_evidence("contradict"), _make_evidence("neutral"),
            ],
        )
        result = node_aggregate(state)
        assert result["verdict"] in ("MIXED", "UNKNOWN")

    def test_trusted_source_weighted_higher(self):
        from agents.supervisor import node_aggregate
        state = GraphState(
            core_claim="Test claim",
            worker_results=[
                _make_evidence("support", source="snopes", trust=1.5),
                _make_evidence("contradict", source="web", trust=1.0),
            ],
        )
        result = node_aggregate(state)
        # Snopes support outweighs web contradict
        assert result["confidence"] > 0.5

    def test_empty_results_gives_unknown(self):
        from agents.supervisor import node_aggregate
        state = GraphState(core_claim="Test claim", worker_results=[])
        result = node_aggregate(state)
        assert result["verdict"] == "UNKNOWN"
        assert result["confidence"] == 0.0


# ── Unit: Router Logic ─────────────────────────────────────────────────────────

class TestRoutingLogic:
    def test_low_confidence_depth_0_recurses(self):
        from agents.supervisor import route_after_aggregate
        state = GraphState(core_claim="Test", confidence=0.4, depth=0)
        # Router now routes to increment_depth node (not directly to fan_out)
        assert route_after_aggregate(state) == "increment_depth"

    def test_high_confidence_goes_to_judge(self):
        from agents.supervisor import route_after_aggregate
        state = GraphState(core_claim="Test", confidence=0.85, depth=0)
        # High confidence → skip recursion → go to Final Judge node
        assert route_after_aggregate(state) == "node_judge"

    def test_max_depth_always_goes_to_judge(self):
        from agents.supervisor import route_after_aggregate
        state = GraphState(core_claim="Test", confidence=0.1, depth=3)
        # depth == MAX_DEPTH → no more recursion → go to Final Judge node
        assert route_after_aggregate(state) == "node_judge"


# ── Unit: Categorisation ───────────────────────────────────────────────────────

class TestCategorisation:
    def test_political_claim(self):
        from agents.supervisor import node_categorize
        state = GraphState(core_claim="The president signed the bill.")
        assert node_categorize(state)["category"] == "political"

    def test_scientific_claim(self):
        from agents.supervisor import node_categorize
        state = GraphState(core_claim="The vaccine causes autism.")
        assert node_categorize(state)["category"] == "scientific"

    def test_economic_claim(self):
        from agents.supervisor import node_categorize
        state = GraphState(core_claim="GDP grew by 4% last quarter.")
        assert node_categorize(state)["category"] == "economic"

    def test_unknown_claim(self):
        from agents.supervisor import node_categorize
        state = GraphState(core_claim="The sky looks nice today.")
        assert node_categorize(state)["category"] == "other"


# ── Integration: Graph Compilation ────────────────────────────────────────────

class TestGraphCompilation:
    def test_graph_compiles_without_error(self):
        """This is the MT-5 verification rule: graph must compile without deadlocks."""
        from agents.supervisor import _graph
        assert _graph is not None

    def test_graph_has_expected_nodes(self):
        from agents.supervisor import _graph
        nodes = set(_graph.get_graph().nodes.keys())
        for expected in {"extract", "categorize", "fan_out", "aggregate", "node_judge", "synthesize"}:
            assert expected in nodes, f"Missing node: {expected}"


# ── Integration: Full Pipeline (mocked) ───────────────────────────────────────

class TestFullPipeline:
    @patch("agents.agent1_extractor._get_client")
    @patch("agents.supervisor.search_web", return_value=[
        {"source": "web", "stance": "contradict", "excerpt": "False claim debunked.", "url": "https://debunk.com", "trust_weight": 1.0},
    ])
    @patch("agents.supervisor.search_trusted_dbs", return_value=[
        {"source": "snopes", "stance": "contradict", "excerpt": "Snopes: FALSE", "url": "https://snopes.com/test", "trust_weight": 1.5},
    ])
    @patch("agents.supervisor.search_social", return_value=[])
    @patch("agents.supervisor.analyze_multimodal", return_value=[])
    @patch("agents.supervisor.node_judge", return_value={
        "verdict": "FALSE",
        "confidence": 0.15,
        "summary": "The claim is debunked by multiple sources.",
        "source_url": "https://snopes.com/test",
    })
    def test_pipeline_returns_false_for_flat_earth(
        self,
        _mock_judge,
        _mock_multimodal,
        _mock_social,
        _mock_trusted,
        _mock_web,
        mock_get_client,
    ):
        """Full graph traversal with mocked Gemini + mocked workers."""
        from agents.supervisor import run_pipeline

        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "transcript": "The Earth is flat.",
            "core_claim": "The Earth is flat.",
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = run_pipeline(b"\x00" * 100)

        assert result is not None
        assert result["claimText"] == "The Earth is flat."
        assert result["claimVeracity"] == "falseVerdict"  # FALSE maps to falseVerdict
        assert 0.0 <= result["confidenceScore"] <= 1.0
        assert result["summaryAndExplanation"] != ""
        assert "id" in result

    @patch("agents.agent1_extractor._get_client")
    def test_pipeline_returns_none_for_empty_claim(self, mock_get_client):
        """Pipeline should return None when no claim is found in audio."""
        from agents.supervisor import run_pipeline

        mock_response = MagicMock()
        mock_response.text = json.dumps({"transcript": "Um, nice weather.", "core_claim": ""})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = run_pipeline(b"\x00" * 100)
        assert result is None
