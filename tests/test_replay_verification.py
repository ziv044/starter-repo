"""Tests for session replay and behavior verification (FR42)."""

import json
import tempfile
from pathlib import Path

import pytest

from pm6.state.sessionReplayer import (
    ReplayInteraction,
    ReplayVerificationResult,
    ReplayVerifier,
    ResponseComparison,
    SessionReplayer,
    defaultResponseComparator,
)


class TestResponseComparison:
    """Tests for ResponseComparison dataclass."""

    def test_create_comparison(self):
        """Test creating a response comparison."""
        comparison = ResponseComparison(
            index=0,
            agentName="pm",
            userInput="Hello",
            originalResponse="Hi there!",
            replayedResponse="Hi there!",
            match=True,
            similarity=1.0,
        )
        assert comparison.match
        assert comparison.similarity == 1.0

    def test_comparison_with_drift(self):
        """Test comparison where responses differ."""
        comparison = ResponseComparison(
            index=1,
            agentName="pm",
            userInput="What's the plan?",
            originalResponse="We need to focus on the economy.",
            replayedResponse="Let me think about that.",
            match=False,
            similarity=0.3,
        )
        assert not comparison.match
        assert comparison.similarity == 0.3


class TestReplayVerificationResult:
    """Tests for ReplayVerificationResult dataclass."""

    def test_create_result(self):
        """Test creating a verification result."""
        comparisons = [
            ResponseComparison(
                index=0, agentName="pm", userInput="Hi",
                originalResponse="Hello", replayedResponse="Hello",
                match=True, similarity=1.0,
            ),
            ResponseComparison(
                index=1, agentName="pm", userInput="Bye",
                originalResponse="Goodbye", replayedResponse="See ya",
                match=False, similarity=0.5,
            ),
        ]
        result = ReplayVerificationResult(
            sessionId="test_session",
            totalInteractions=2,
            matchingResponses=1,
            driftedResponses=1,
            comparisons=comparisons,
            passed=False,
            driftThreshold=0.0,
            actualDriftRate=0.5,
        )
        assert result.totalInteractions == 2
        assert result.matchingResponses == 1
        assert result.driftedResponses == 1
        assert not result.passed

    def test_get_drifted_interactions(self):
        """Test filtering to drifted interactions."""
        comparisons = [
            ResponseComparison(
                index=0, agentName="pm", userInput="Hi",
                originalResponse="Hello", replayedResponse="Hello",
                match=True,
            ),
            ResponseComparison(
                index=1, agentName="pm", userInput="Bye",
                originalResponse="Goodbye", replayedResponse="Later",
                match=False,
            ),
        ]
        result = ReplayVerificationResult(
            sessionId="test",
            totalInteractions=2,
            matchingResponses=1,
            driftedResponses=1,
            comparisons=comparisons,
            passed=False,
        )
        drifted = result.getDriftedInteractions()
        assert len(drifted) == 1
        assert drifted[0].index == 1

    def test_get_matched_interactions(self):
        """Test filtering to matched interactions."""
        comparisons = [
            ResponseComparison(
                index=0, agentName="pm", userInput="Hi",
                originalResponse="Hello", replayedResponse="Hello",
                match=True,
            ),
            ResponseComparison(
                index=1, agentName="pm", userInput="Bye",
                originalResponse="Goodbye", replayedResponse="Goodbye",
                match=True,
            ),
        ]
        result = ReplayVerificationResult(
            sessionId="test",
            totalInteractions=2,
            matchingResponses=2,
            driftedResponses=0,
            comparisons=comparisons,
            passed=True,
        )
        matched = result.getMatchedInteractions()
        assert len(matched) == 2

    def test_to_dict(self):
        """Test conversion to dictionary."""
        comparisons = [
            ResponseComparison(
                index=0, agentName="pm", userInput="Hi",
                originalResponse="Hello", replayedResponse="Hello",
                match=True, similarity=1.0,
            ),
        ]
        result = ReplayVerificationResult(
            sessionId="test",
            totalInteractions=1,
            matchingResponses=1,
            driftedResponses=0,
            comparisons=comparisons,
            passed=True,
            driftThreshold=0.1,
            actualDriftRate=0.0,
        )
        data = result.toDict()
        assert data["sessionId"] == "test"
        assert data["passed"]
        assert len(data["comparisons"]) == 1


class TestDefaultResponseComparator:
    """Tests for the default comparator function."""

    def test_exact_match(self):
        """Test exact match comparison."""
        match, similarity = defaultResponseComparator("Hello", "Hello")
        assert match
        assert similarity == 1.0

    def test_whitespace_ignored(self):
        """Test that leading/trailing whitespace is ignored."""
        match, similarity = defaultResponseComparator("  Hello  ", "Hello")
        assert match
        assert similarity == 1.0

    def test_no_match(self):
        """Test non-matching responses."""
        match, similarity = defaultResponseComparator("Hello", "Goodbye")
        assert not match
        assert similarity == 0.0


class TestSessionReplayer:
    """Tests for SessionReplayer."""

    def _create_session_file(self, tmpdir: str, sessionId: str, interactions: list):
        """Helper to create a session file."""
        sessionsPath = Path(tmpdir) / "test_sim" / "sessions"
        sessionsPath.mkdir(parents=True, exist_ok=True)

        sessionData = {
            "metadata": {"sessionId": sessionId},
            "interactions": interactions,
        }

        with open(sessionsPath / f"{sessionId}.json", "w") as f:
            json.dump(sessionData, f)

    def test_load_and_iterate(self):
        """Test loading and iterating a session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "pm", "userInput": "Bye", "response": "Goodbye"},
            ]
            self._create_session_file(tmpdir, "session1", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")
            replayer.loadSession("session1")

            results = list(replayer.iterate())
            assert len(results) == 2
            assert results[0].userInput == "Hi"
            assert results[1].response == "Goodbye"

    def test_seek_and_current(self):
        """Test seeking to specific position."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "One", "response": "1"},
                {"agentName": "pm", "userInput": "Two", "response": "2"},
                {"agentName": "pm", "userInput": "Three", "response": "3"},
            ]
            self._create_session_file(tmpdir, "session2", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")
            replayer.loadSession("session2")

            replayer.seekTo(1)
            current = replayer.current()
            assert current.userInput == "Two"

    def test_find_interactions(self):
        """Test finding interactions by criteria."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "chancellor", "userInput": "Budget?", "response": "1.2T"},
                {"agentName": "pm", "userInput": "Thanks", "response": "You're welcome"},
            ]
            self._create_session_file(tmpdir, "session3", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")
            replayer.loadSession("session3")

            pm_interactions = replayer.findInteractions(agentName="pm")
            assert len(pm_interactions) == 2


class TestReplayVerifier:
    """Tests for ReplayVerifier."""

    def _create_session_file(self, tmpdir: str, sessionId: str, interactions: list):
        """Helper to create a session file."""
        sessionsPath = Path(tmpdir) / "test_sim" / "sessions"
        sessionsPath.mkdir(parents=True, exist_ok=True)

        sessionData = {
            "metadata": {"sessionId": sessionId},
            "interactions": interactions,
        }

        with open(sessionsPath / f"{sessionId}.json", "w") as f:
            json.dump(sessionData, f)

    def test_verify_matching_session(self):
        """Test verifying a session with consistent responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "pm", "userInput": "Bye", "response": "Goodbye"},
            ]
            self._create_session_file(tmpdir, "consistent", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")

            # Mock generator that returns same responses
            def mock_generator(agent, input, worldState):
                if input == "Hi":
                    return "Hello"
                return "Goodbye"

            verifier = ReplayVerifier(replayer, mock_generator)
            result = verifier.verify("consistent")

            assert result.passed
            assert result.totalInteractions == 2
            assert result.matchingResponses == 2
            assert result.driftedResponses == 0
            assert result.actualDriftRate == 0.0

    def test_verify_drifted_session(self):
        """Test verifying a session with behavioral drift."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "pm", "userInput": "Bye", "response": "Goodbye"},
            ]
            self._create_session_file(tmpdir, "drifted", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")

            # Mock generator that returns different responses
            def mock_generator(agent, input, worldState):
                return "Different response"

            verifier = ReplayVerifier(replayer, mock_generator)
            result = verifier.verify("drifted")

            assert not result.passed
            assert result.driftedResponses == 2
            assert result.actualDriftRate == 1.0

    def test_verify_with_threshold(self):
        """Test verifying with allowed drift threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "pm", "userInput": "Question", "response": "Answer"},
            ]
            self._create_session_file(tmpdir, "partial", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")

            # One matching, one different
            def mock_generator(agent, input, worldState):
                if input == "Hi":
                    return "Hello"
                return "Different answer"

            verifier = ReplayVerifier(replayer, mock_generator)

            # 50% drift, threshold 0.5 - should pass
            result = verifier.verify("partial", driftThreshold=0.5)
            assert result.passed
            assert result.actualDriftRate == 0.5

            # 50% drift, threshold 0.25 - should fail
            result = verifier.verify("partial", driftThreshold=0.25)
            assert not result.passed

    def test_verify_with_agent_filter(self):
        """Test verifying only specific agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "Hello"},
                {"agentName": "chancellor", "userInput": "Budget?", "response": "1.2T"},
                {"agentName": "pm", "userInput": "Thanks", "response": "Welcome"},
            ]
            self._create_session_file(tmpdir, "multi_agent", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")

            # Mock that matches PM but not Chancellor
            def mock_generator(agent, input, worldState):
                if agent == "pm":
                    if input == "Hi":
                        return "Hello"
                    return "Welcome"
                return "Wrong answer"

            verifier = ReplayVerifier(replayer, mock_generator)

            # Only verify PM - should pass
            result = verifier.verify("multi_agent", agentFilter="pm")
            assert result.passed
            assert result.totalInteractions == 2  # Only PM interactions

            # Verify all - should fail due to Chancellor
            result = verifier.verify("multi_agent")
            assert not result.passed

    def test_verify_with_custom_comparator(self):
        """Test verifying with custom comparison logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            interactions = [
                {"agentName": "pm", "userInput": "Hi", "response": "HELLO"},
            ]
            self._create_session_file(tmpdir, "case_test", interactions)

            replayer = SessionReplayer(Path(tmpdir), "test_sim")

            def mock_generator(agent, input, worldState):
                return "hello"

            # Case-insensitive comparator
            def case_insensitive(original, replayed):
                match = original.lower() == replayed.lower()
                return match, 1.0 if match else 0.0

            verifier = ReplayVerifier(replayer, mock_generator)

            # Default (case-sensitive) should fail
            result = verifier.verify("case_test")
            assert not result.passed

            # Custom (case-insensitive) should pass
            result = verifier.verify("case_test", comparator=case_insensitive)
            assert result.passed
