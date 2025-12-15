"""Tests for LLMLogger."""

import json
import os
from pathlib import Path

import pytest

from pm6 import LLMLogger, get_settings, reset_settings


def test_logger_creates_session_file(tmp_path: Path, monkeypatch):
    """Test that logger creates a session file."""
    monkeypatch.setenv("PM6_LOG_DIR", str(tmp_path))
    reset_settings()

    logger = LLMLogger("test_session")

    assert logger.session_path.parent == tmp_path
    assert "test_session_001.jsonl" in str(logger.session_path)


def test_logger_auto_increment(tmp_path: Path, monkeypatch):
    """Test that logger auto-increments session names."""
    monkeypatch.setenv("PM6_LOG_DIR", str(tmp_path))
    reset_settings()

    # Create first session file
    (tmp_path / "test_session_001.jsonl").touch()

    logger = LLMLogger("test_session")

    assert "test_session_002.jsonl" in str(logger.session_path)


def test_logger_log_entry(tmp_path: Path, monkeypatch):
    """Test logging an entry."""
    monkeypatch.setenv("PM6_LOG_DIR", str(tmp_path))
    reset_settings()

    logger = LLMLogger("test_session")
    logger.log(
        agent_name="my_agent",
        request={"model": "claude-sonnet-4-20250514", "messages": []},
        response={"content": [{"text": "Hello"}]},
        duration_ms=100,
    )

    # Read and verify the log
    with open(logger.session_path, "r") as f:
        entry = json.loads(f.readline())

    assert entry["agent_name"] == "my_agent"
    assert entry["call_index"] == 1
    assert entry["duration_ms"] == 100
    assert "timestamp" in entry


def test_logger_call_count(tmp_path: Path, monkeypatch):
    """Test call count tracking."""
    monkeypatch.setenv("PM6_LOG_DIR", str(tmp_path))
    reset_settings()

    logger = LLMLogger("test_session")

    # Log multiple calls for same agent
    for _ in range(3):
        logger.log("agent_a", {}, {}, 100)

    # Log for different agent
    logger.log("agent_b", {}, {}, 100)

    assert logger.get_call_count("agent_a") == 3
    assert logger.get_call_count("agent_b") == 1
    assert logger.get_call_count("unknown") == 0
