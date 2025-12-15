"""Shared pytest fixtures for pm6 tests."""

import os
from pathlib import Path

import pytest

from pm6 import reset_settings


@pytest.fixture(autouse=True)
def reset_env():
    """Reset settings and environment before each test."""
    reset_settings()
    # Clear any PM6 env vars that might interfere
    for key in list(os.environ.keys()):
        if key.startswith("PM6_"):
            del os.environ[key]
    yield
    reset_settings()


@pytest.fixture
def tmp_log_dir(tmp_path: Path) -> Path:
    """Create a temporary log directory."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def sample_session(tmp_path: Path) -> Path:
    """Create a sample session file for replay tests."""
    import json

    session_path = tmp_path / "test_session_001.jsonl"
    entries = [
        {
            "timestamp": "2025-12-15T10:00:00.000Z",
            "agent_name": "test_agent",
            "call_index": 1,
            "request": {"model": "claude-sonnet-4-20250514", "messages": []},
            "response": {"content": [{"text": "Hello!"}]},
            "duration_ms": 100,
        },
        {
            "timestamp": "2025-12-15T10:00:01.000Z",
            "agent_name": "test_agent",
            "call_index": 2,
            "request": {"model": "claude-sonnet-4-20250514", "messages": []},
            "response": {"content": [{"text": "Goodbye!"}]},
            "duration_ms": 150,
        },
        {
            "timestamp": "2025-12-15T10:00:02.000Z",
            "agent_name": "other_agent",
            "call_index": 1,
            "request": {"model": "claude-sonnet-4-20250514", "messages": []},
            "response": {"content": [{"text": "Other response"}]},
            "duration_ms": 200,
        },
    ]

    with open(session_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return session_path
