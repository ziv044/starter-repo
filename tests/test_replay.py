"""Tests for LLMReplayProvider."""

from pathlib import Path

import pytest

from pm6 import (
    LLMReplayProvider,
    ReplayNotFoundError,
    SessionNotFoundError,
    get_settings,
    reset_settings,
)


def test_replay_load_session(sample_session: Path):
    """Test loading a session file."""
    provider = LLMReplayProvider(sample_session)

    assert provider.total_entries == 3
    assert set(provider.agent_names) == {"test_agent", "other_agent"}


def test_replay_not_found():
    """Test error when session file doesn't exist."""
    with pytest.raises(SessionNotFoundError) as exc:
        LLMReplayProvider("/nonexistent/path.jsonl")

    assert "not found" in str(exc.value)


def test_replay_get_response_sequential(sample_session: Path):
    """Test sequential response retrieval."""
    provider = LLMReplayProvider(sample_session)

    # First call for test_agent
    response1 = provider.get_response("test_agent")
    assert response1["content"][0]["text"] == "Hello!"

    # Second call for test_agent
    response2 = provider.get_response("test_agent")
    assert response2["content"][0]["text"] == "Goodbye!"


def test_replay_different_agents(sample_session: Path):
    """Test responses for different agents are independent."""
    provider = LLMReplayProvider(sample_session)

    # Get response for other_agent
    response = provider.get_response("other_agent")
    assert response["content"][0]["text"] == "Other response"

    # test_agent should still get its first response
    response = provider.get_response("test_agent")
    assert response["content"][0]["text"] == "Hello!"


def test_replay_not_found_strict(sample_session: Path, monkeypatch):
    """Test strict mode raises on missing response."""
    monkeypatch.setenv("PM6_STRICT_REPLAY", "true")
    reset_settings()

    provider = LLMReplayProvider(sample_session)

    # Exhaust all responses for test_agent
    provider.get_response("test_agent")
    provider.get_response("test_agent")

    with pytest.raises(ReplayNotFoundError) as exc:
        provider.get_response("test_agent")

    assert exc.value.agent_name == "test_agent"
    assert exc.value.call_index == 3


def test_replay_not_found_non_strict(sample_session: Path, monkeypatch):
    """Test non-strict mode returns empty dict on missing response."""
    monkeypatch.setenv("PM6_STRICT_REPLAY", "false")
    reset_settings()

    provider = LLMReplayProvider(sample_session)

    # Exhaust all responses
    provider.get_response("test_agent")
    provider.get_response("test_agent")

    # Should return empty dict instead of raising
    response = provider.get_response("test_agent")
    assert response == {}


def test_replay_has_response(sample_session: Path):
    """Test checking if response is available."""
    provider = LLMReplayProvider(sample_session)

    assert provider.has_response("test_agent") is True
    provider.get_response("test_agent")

    assert provider.has_response("test_agent") is True
    provider.get_response("test_agent")

    assert provider.has_response("test_agent") is False


def test_replay_reset(sample_session: Path):
    """Test resetting replay indices."""
    provider = LLMReplayProvider(sample_session)

    # Use up first response
    provider.get_response("test_agent")

    # Reset and should get first response again
    provider.reset("test_agent")
    response = provider.get_response("test_agent")
    assert response["content"][0]["text"] == "Hello!"


def test_replay_agent_call_count(sample_session: Path):
    """Test getting agent call count."""
    provider = LLMReplayProvider(sample_session)

    assert provider.get_agent_call_count("test_agent") == 2
    assert provider.get_agent_call_count("other_agent") == 1
    assert provider.get_agent_call_count("unknown") == 0
