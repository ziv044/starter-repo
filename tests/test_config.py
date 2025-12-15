"""Tests for Settings configuration."""

import os
from pathlib import Path

import pytest

from pm6 import Mode, Settings, get_settings, reset_settings


def test_default_settings():
    """Test default settings values."""
    settings = Settings()
    assert settings.mode == Mode.LIVE
    assert settings.strict_replay is True
    assert settings.default_model == "claude-sonnet-4-20250514"


def test_settings_from_env(tmp_path: Path, monkeypatch):
    """Test settings loaded from environment variables."""
    monkeypatch.setenv("PM6_MODE", "REPLAY")
    monkeypatch.setenv("PM6_STRICT_REPLAY", "false")
    monkeypatch.setenv("PM6_LOG_DIR", str(tmp_path / "custom_logs"))

    reset_settings()
    settings = get_settings()

    assert settings.mode == Mode.REPLAY
    assert settings.strict_replay is False
    assert "custom_logs" in str(settings.log_dir)


def test_get_settings_singleton():
    """Test that get_settings returns the same instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2


def test_reset_settings():
    """Test that reset_settings clears the singleton."""
    settings1 = get_settings()
    reset_settings()
    settings2 = get_settings()
    assert settings1 is not settings2


def test_log_dir_created(tmp_path: Path, monkeypatch):
    """Test that log directory is created on init."""
    log_dir = tmp_path / "new_logs"
    assert not log_dir.exists()

    monkeypatch.setenv("PM6_LOG_DIR", str(log_dir))
    reset_settings()
    settings = get_settings()

    assert log_dir.exists()
