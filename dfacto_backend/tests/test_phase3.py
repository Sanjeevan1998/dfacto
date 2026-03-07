"""
Phase 3 Tests — MT-25

Covers:
- Agent 2a (worker_web): TavilySearch response parsing, keyword stance, Gemini stance
- Agent 2c (worker_social): Reddit JSON parsing, keyword stance, graceful failures
- Agent 2b (worker_multimodal): Tavily + Gemini analysis path, empty response handling
- Agent 2d (worker_trusted): Tavily include_domains, keyword stance
- Agent 2e (node_judge): 6-category verdict, Gemini parse, fallback
- Veracity map: all 6 verdicts → correct Flutter keys
- ContextWindow: pointer advance, never-discard invariant

All tests run WITHOUT a real API key (Gemini/Tavily/Reddit mocked).
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from models.state import GraphState, EvidenceItem


# ── Agent 2a: Web Worker (Tavily) ─────────────────────────────────────────────

class TestWorkerWeb:
    def _mock_tavily_response(self, items: list[dict]) -> dict:
        return {"results": items, "query": "test", "answer": None}

    @patch("agents.worker_web.TavilySearch")
    @patch("agents.worker_web._get_client")
    def test_tavily_results_parsed_correctly(self, mock_get_client, mock_tavily_cls):
        """TavilySearch dict response is unpacked from 'results' key."""
        from agents.worker_web import search_web

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = self._mock_tavily_response([
            {"url": "https://fact.com/1", "content": "The claim is verified as true."},
        ])
        mock_tavily_cls.return_value = mock_tool

        mock_resp = MagicMock()
        mock_resp.text = json.dumps({"stance": "support", "excerpt": "Verified true."})
        mock_get_client.return_value.models.generate_content.return_value = mock_resp

        results = search_web("Neil Armstrong walked on the Moon")
        assert len(results) == 1
        assert results[0]["stance"] == "support"
        assert results[0]["url"] == "https://fact.com/1"
        assert results[0]["trust_weight"] == 1.0

    @patch("agents.worker_web.TavilySearch")
    def test_tavily_empty_results_returns_empty_list(self, mock_tavily_cls):
        from agents.worker_web import search_web
        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {"results": []}
        mock_tavily_cls.return_value = mock_tool
        results = search_web("some claim")
        assert results == []

    @patch("agents.worker_web.TavilySearch")
    def test_tavily_error_returns_empty_list(self, mock_tavily_cls):
        from agents.worker_web import search_web
        mock_tavily_cls.return_value.invoke.side_effect = Exception("network error")
        results = search_web("some claim")
        assert results == []

    @patch("agents.worker_web.TavilySearch")
    @patch("agents.worker_web._get_client")
    def test_keyword_stance_fallback_when_gemini_fails(self, mock_get_client, mock_tavily_cls):
        """When Gemini stance fails, keyword scan is used as fallback."""
        from agents.worker_web import search_web

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = self._mock_tavily_response([
            {"url": "https://fact.com/1", "content": "This claim is completely debunked and false."},
        ])
        mock_tavily_cls.return_value = mock_tool
        mock_get_client.return_value.models.generate_content.side_effect = Exception("api error")

        results = search_web("some claim")
        assert len(results) == 1
        assert results[0]["stance"] == "contradict"

    def test_empty_claim_returns_empty_list(self):
        from agents.worker_web import search_web
        assert search_web("") == []
        assert search_web("   ") == []


# ── Agent 2c: Social Worker (Reddit) ─────────────────────────────────────────

class TestWorkerSocial:
    def _make_reddit_response(self, posts: list[dict]) -> bytes:
        data = {
            "data": {
                "children": [{"kind": "t3", "data": p} for p in posts]
            }
        }
        return json.dumps(data).encode()

    @patch("agents.worker_social.urllib.request.urlopen")
    def test_reddit_returns_support_stance(self, mock_urlopen):
        from agents.worker_social import search_social
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._make_reddit_response([
            {
                "title": "Vaccines confirmed safe and effective by WHO",
                "selftext": "New verified study proves vaccine efficacy.",
                "url": "https://reddit.com/r/factcheck/test",
                "permalink": "/r/factcheck/test",
            }
        ])
        mock_urlopen.return_value.__enter__ = lambda s: mock_resp
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = search_social("Vaccines are safe")
        assert len(results) >= 1
        assert results[0]["stance"] == "support"
        assert results[0]["trust_weight"] == 0.6

    @patch("agents.worker_social.urllib.request.urlopen")
    def test_reddit_returns_contradict_stance(self, mock_urlopen):
        from agents.worker_social import search_social
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._make_reddit_response([
            {
                "title": "Claim debunked and confirmed as misinformation",
                "selftext": "This is completely false and fabricated.",
                "url": "https://reddit.com/r/skeptic/test",
                "permalink": "/r/skeptic/test",
            }
        ])
        mock_urlopen.return_value.__enter__ = lambda s: mock_resp
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = search_social("The Earth is flat")
        assert results[0]["stance"] == "contradict"

    @patch("agents.worker_social.urllib.request.urlopen")
    def test_reddit_network_error_returns_empty(self, mock_urlopen):
        from agents.worker_social import search_social
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        results = search_social("some claim")
        assert results == []

    def test_empty_claim_returns_empty(self):
        from agents.worker_social import search_social
        assert search_social("") == []

    @patch("agents.worker_social.urllib.request.urlopen")
    def test_max_three_results_returned(self, mock_urlopen):
        from agents.worker_social import search_social
        posts = [
            {"title": f"Post {i}", "selftext": "", "url": f"https://r/{i}", "permalink": f"/r/factcheck/{i}"}
            for i in range(5)
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._make_reddit_response(posts)
        mock_urlopen.return_value.__enter__ = lambda s: mock_resp
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)

        results = search_social("some claim")
        assert len(results) <= 3


# ── Agent 2b: Multimodal Worker ───────────────────────────────────────────────

class TestWorkerMultimodal:
    @patch("agents.worker_multimodal.TavilySearch")
    @patch("agents.worker_multimodal._get_client")
    def test_multimodal_returns_analysis_item(self, mock_get_client, mock_tavily_cls):
        from agents.worker_multimodal import analyze_multimodal

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {
            "results": [
                {"url": "https://analysis.com/1", "content": "Extensive research confirms this claim."},
                {"url": "https://analysis.com/2", "content": "Multiple studies show supporting evidence."},
            ]
        }
        mock_tavily_cls.return_value = mock_tool

        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "stance": "support",
            "confidence": 0.85,
            "key_finding": "Research confirms this claim.",
            "nuance": "Some minor caveats apply.",
        })
        mock_get_client.return_value.models.generate_content.return_value = mock_resp

        results = analyze_multimodal("Neil Armstrong walked on the Moon in 1969")
        assert len(results) == 1
        assert results[0]["stance"] == "support"
        assert results[0]["trust_weight"] == 1.2
        assert results[0]["source"] == "multimodal_analysis"

    @patch("agents.worker_multimodal.TavilySearch")
    def test_empty_tavily_returns_empty(self, mock_tavily_cls):
        from agents.worker_multimodal import analyze_multimodal
        mock_tavily_cls.return_value.invoke.return_value = {"results": []}
        results = analyze_multimodal("some claim")
        assert results == []

    def test_empty_claim_returns_empty(self):
        from agents.worker_multimodal import analyze_multimodal
        assert analyze_multimodal("") == []


# ── Agent 2d: Trusted DB Worker (Tavily include_domains) ─────────────────────

class TestWorkerTrusted:
    @patch("agents.worker_trusted.TavilySearch")
    def test_trusted_returns_contradict_for_debunked_content(self, mock_tavily_cls):
        from agents.worker_trusted import search_trusted_dbs

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {
            "results": [
                {"url": "https://snopes.com/claim-debunked", "content": "Pants on Fire: This claim is false and debunked."},
            ]
        }
        mock_tavily_cls.return_value = mock_tool

        results = search_trusted_dbs("The Earth is flat")
        assert len(results) == 1
        assert results[0]["stance"] == "contradict"
        assert results[0]["trust_weight"] == 1.5
        assert results[0]["source"] == "snopes"

    @patch("agents.worker_trusted.TavilySearch")
    def test_trusted_returns_support_for_confirmed_content(self, mock_tavily_cls):
        from agents.worker_trusted import search_trusted_dbs

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = {
            "results": [
                {"url": "https://factcheck.org/claim-true", "content": "This claim is confirmed and verified as accurate."},
            ]
        }
        mock_tavily_cls.return_value = mock_tool

        results = search_trusted_dbs("Neil Armstrong walked on the Moon")
        assert results[0]["stance"] == "support"
        assert results[0]["source"] == "factcheck"

    @patch("agents.worker_trusted.TavilySearch")
    def test_trusted_error_returns_empty(self, mock_tavily_cls):
        from agents.worker_trusted import search_trusted_dbs
        mock_tavily_cls.return_value.invoke.side_effect = Exception("api error")
        results = search_trusted_dbs("some claim")
        assert results == []

    def test_empty_claim_returns_empty(self):
        from agents.worker_trusted import search_trusted_dbs
        assert search_trusted_dbs("") == []


# ── Agent 2e: Final Judge (6-category verdict) ────────────────────────────────

class TestFinalJudge:
    def _make_state(self, verdict: str, confidence: float, items: list[EvidenceItem]) -> GraphState:
        return GraphState(
            core_claim="Test claim for judging",
            verdict=verdict,
            confidence=confidence,
            worker_results=items,
        )

    @patch("agents.supervisor._get_gemini_client")
    def test_judge_returns_six_category_verdict(self, mock_get_client):
        from agents.supervisor import node_judge

        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "verdict": "MOSTLY TRUE",
            "confidence": 0.78,
            "explanation": "The claim is mostly accurate with minor nuances.",
            "key_source": "https://snopes.com/test",
        })
        mock_get_client.return_value.models.generate_content.return_value = mock_resp

        state = self._make_state("TRUE", 0.75, [
            EvidenceItem(source="web", stance="support", excerpt="Confirmed.", url="https://web.com", trust_weight=1.0),
        ])
        result = node_judge(state)
        assert result["verdict"] == "MOSTLY TRUE"
        assert result["confidence"] == 0.78
        assert isinstance(result["summary"], str) and len(result["summary"]) > 0

    @patch("agents.supervisor._get_gemini_client")
    def test_judge_handles_gemini_failure_gracefully(self, mock_get_client):
        from agents.supervisor import node_judge
        mock_get_client.return_value.models.generate_content.side_effect = Exception("api error")

        state = self._make_state("FALSE", 0.20, [
            EvidenceItem(source="snopes", stance="contradict", excerpt="Debunked.", url="https://snopes.com", trust_weight=1.5),
        ])
        result = node_judge(state)
        # Falls back gracefully — doesn't crash, returns summary from excerpts
        assert isinstance(result, dict)
        assert "summary" in result

    def test_judge_returns_empty_dict_for_no_claim(self):
        from agents.supervisor import node_judge
        state = GraphState(core_claim="", worker_results=[])
        result = node_judge(state)
        assert result == {}

    @patch("agents.supervisor._get_gemini_client")
    def test_judge_strips_markdown_fences(self, mock_get_client):
        from agents.supervisor import node_judge
        mock_resp = MagicMock()
        payload = {"verdict": "HALF TRUE", "confidence": 0.50,
                   "explanation": "Mixed evidence.", "key_source": "https://ex.com"}
        mock_resp.text = "```json\n" + json.dumps(payload) + "\n```"
        mock_get_client.return_value.models.generate_content.return_value = mock_resp

        state = self._make_state("MIXED", 0.50, [
            EvidenceItem(source="web", stance="neutral", excerpt="Mixed.", url="https://ex.com"),
        ])
        result = node_judge(state)
        assert result["verdict"] == "HALF TRUE"


# ── Veracity Map: 6-category → Flutter keys ───────────────────────────────────

class TestVeracityMap:
    """Verifies all 6 verdict strings map to correct Flutter claimVeracity values."""

    def _format(self, verdict: str, confidence: float = 0.5) -> dict:
        from agents.supervisor import _format_result
        state_dict = {
            "core_claim": "Test claim",
            "verdict": verdict,
            "confidence": confidence,
            "summary": "Test summary",
            "source_url": None,
            "worker_results": [],
            "transcript": "",
            "category": "other",
            "depth": 0,
            "audio_chunk": b"",
        }
        return _format_result(state_dict)

    def test_true_verdict(self):
        assert self._format("TRUE")["claimVeracity"] == "trueVerdict"

    def test_mostly_true_verdict(self):
        assert self._format("MOSTLY TRUE")["claimVeracity"] == "mostlyTrue"

    def test_half_true_verdict(self):
        assert self._format("HALF TRUE")["claimVeracity"] == "halfTrue"

    def test_mostly_false_verdict(self):
        assert self._format("MOSTLY FALSE")["claimVeracity"] == "mostlyFalse"

    def test_false_verdict(self):
        assert self._format("FALSE")["claimVeracity"] == "falseVerdict"

    def test_unverifiable_verdict(self):
        assert self._format("UNVERIFIABLE")["claimVeracity"] == "unknown"

    def test_legacy_mixed_maps_to_half_true(self):
        assert self._format("MIXED")["claimVeracity"] == "halfTrue"

    def test_legacy_unknown_maps_to_unknown(self):
        assert self._format("UNKNOWN")["claimVeracity"] == "unknown"


# ── ContextWindow: never-discard invariant ────────────────────────────────────

class TestContextWindow:
    def test_words_are_never_deleted(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        cw.add("hello world")
        cw.advance_check_pointer()
        cw.add("new words added")
        # Full context still contains all words
        assert "hello" in cw.full_context_snapshot()
        assert "new" in cw.full_context_snapshot()

    def test_new_window_only_shows_post_pointer_words(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        cw.add("first batch of words")
        cw.advance_check_pointer()
        cw.add("second batch of words")
        assert "first" not in cw.new_window_snapshot()
        assert "second" in cw.new_window_snapshot()

    def test_advance_pointer_tracks_total_words(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        cw.add("one two three four five")  # 5 words
        assert cw.new_word_count == 5
        cw.advance_check_pointer()
        assert cw.new_word_count == 0
        cw.add("six seven")
        assert cw.new_word_count == 2
        assert cw.total_words == 7  # All words still counted

    def test_should_check_on_count_fires_at_threshold(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        # CHUNK_NEW_WORDS = 30; add 30 words
        cw.add(" ".join(["word"] * 30))
        assert cw.should_check_on_count is True

    def test_below_threshold_does_not_fire(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        cw.add(" ".join(["word"] * 5))
        assert cw.should_check_on_count is False

    def test_has_content_false_when_empty(self):
        from routers.live_audit import ContextWindow
        cw = ContextWindow()
        assert cw.has_content is False
        cw.add("something")
        assert cw.has_content is True
