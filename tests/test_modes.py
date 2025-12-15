"""Tests for Mode enum."""

from pm6 import Mode


def test_mode_values():
    """Test that Mode has expected values."""
    assert Mode.LIVE.value == "LIVE"
    assert Mode.REPLAY.value == "REPLAY"
    assert Mode.HYBRID.value == "HYBRID"


def test_mode_from_string():
    """Test creating Mode from string value."""
    assert Mode("LIVE") == Mode.LIVE
    assert Mode("REPLAY") == Mode.REPLAY
    assert Mode("HYBRID") == Mode.HYBRID
