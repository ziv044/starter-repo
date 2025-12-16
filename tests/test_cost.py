"""Tests for the cost module."""

import tempfile
from pathlib import Path

import pytest

from pm6.cost import (
    CostTracker,
    ModelRouter,
    ResponseCache,
    SignatureComponents,
    StateBucketer,
    TaskType,
    computeSignature,
)
from pm6.cost.responseCache import CachedResponse


class TestSignatureCompute:
    """Tests for signature computation."""

    def test_compute_signature_deterministic(self):
        """Test signatures are deterministic."""
        components = SignatureComponents(
            agentName="pm",
            situationType="budget",
            stateBucket="approval:high",
            inputIntent="what is your plan",
        )
        sig1 = computeSignature(components)
        sig2 = computeSignature(components)
        assert sig1 == sig2

    def test_different_inputs_different_signatures(self):
        """Test different inputs produce different signatures."""
        sig1 = computeSignature(
            SignatureComponents(
                agentName="pm",
                situationType="budget",
                stateBucket="approval:high",
                inputIntent="plan",
            )
        )
        sig2 = computeSignature(
            SignatureComponents(
                agentName="pm",
                situationType="budget",
                stateBucket="approval:low",  # Different
                inputIntent="plan",
            )
        )
        assert sig1 != sig2

    def test_signature_is_hex_string(self):
        """Test signature is a valid hex string."""
        sig = computeSignature(
            SignatureComponents(
                agentName="test",
                situationType="test",
                stateBucket="test",
                inputIntent="test",
            )
        )
        assert isinstance(sig, str)
        int(sig, 16)  # Should not raise if valid hex


class TestStateBucketer:
    """Tests for state bucketing."""

    def test_bucket_approval(self):
        """Test bucketing approval values."""
        bucketer = StateBucketer()

        state = {"approval": 25}
        result = bucketer.bucketState(state)
        assert "approval:very_low" in result

        state = {"approval": 75}
        result = bucketer.bucketState(state)
        assert "approval:high" in result

    def test_bucket_multiple_values(self):
        """Test bucketing multiple values."""
        bucketer = StateBucketer()
        state = {"approval": 60, "economy": 20}
        result = bucketer.bucketState(state)
        assert "approval:medium" in result
        assert "economy:growing" in result

    def test_bucket_string_values(self):
        """Test string values are passed through."""
        bucketer = StateBucketer()
        state = {"status": "ACTIVE"}
        result = bucketer.bucketState(state)
        assert "status:active" in result


class TestResponseCache:
    """Tests for response caching."""

    def test_cache_put_and_get(self):
        """Test caching and retrieving a response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(Path(tmpdir))
            response = CachedResponse(
                signature="test123",
                response="This is a test response.",
            )
            cache.put(response)

            retrieved = cache.get("test123")
            assert retrieved is not None
            assert retrieved.response == "This is a test response."

    def test_cache_miss(self):
        """Test cache miss returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(Path(tmpdir))
            assert cache.get("nonexistent") is None

    def test_cache_has(self):
        """Test checking if cache has a signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(Path(tmpdir))
            assert not cache.has("test123")

            response = CachedResponse(signature="test123", response="Test")
            cache.put(response)
            assert cache.has("test123")

    def test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ResponseCache(Path(tmpdir))

            stats = cache.getStats()
            assert stats["signatures"] == 0
            assert stats["totalResponses"] == 0

            cache.put(CachedResponse(signature="sig1", response="r1"))
            cache.put(CachedResponse(signature="sig1", response="r2"))
            cache.put(CachedResponse(signature="sig2", response="r3"))

            stats = cache.getStats()
            assert stats["signatures"] == 2
            assert stats["totalResponses"] == 3


class TestModelRouter:
    """Tests for model routing."""

    def test_default_routing(self):
        """Test default model routing."""
        router = ModelRouter()

        assert "haiku" in router.getModel(TaskType.COMPACTION).lower()
        assert "haiku" in router.getModel(TaskType.SUMMARIZATION).lower()
        assert "sonnet" in router.getModel(TaskType.AGENT_RESPONSE).lower()

    def test_is_haiku_task(self):
        """Test Haiku task detection."""
        router = ModelRouter()
        assert router.isHaikuTask(TaskType.COMPACTION)
        assert router.isHaikuTask(TaskType.SUMMARIZATION)
        assert not router.isHaikuTask(TaskType.AGENT_RESPONSE)

    def test_custom_routing(self):
        """Test custom model routing."""
        router = ModelRouter()
        router.setModel(TaskType.AGENT_RESPONSE, "claude-opus-4-20250514")
        assert router.isOpusTask(TaskType.AGENT_RESPONSE)


class TestCostTracker:
    """Tests for cost tracking."""

    def test_record_interaction(self):
        """Test recording an interaction."""
        tracker = CostTracker()
        tracker.recordInteraction(
            model="claude-sonnet-4-20250514",
            inputTokens=1000,
            outputTokens=500,
        )

        stats = tracker.getStats()
        assert stats["totalInteractions"] == 1
        assert stats["totalInputTokens"] == 1000
        assert stats["totalOutputTokens"] == 500
        assert stats["totalCost"] > 0

    def test_cache_hit_tracking(self):
        """Test cache hit tracking."""
        tracker = CostTracker()
        tracker.recordCacheHit()
        tracker.recordInteraction(
            model="claude-sonnet-4-20250514",
            inputTokens=1000,
            outputTokens=500,
        )

        stats = tracker.getStats()
        assert stats["cacheHits"] == 1
        assert stats["cacheMisses"] == 1
        assert stats["cacheHitRate"] == 0.5

    def test_reset(self):
        """Test resetting statistics."""
        tracker = CostTracker()
        tracker.recordInteraction(
            model="claude-sonnet-4-20250514",
            inputTokens=1000,
            outputTokens=500,
        )
        tracker.reset()

        stats = tracker.getStats()
        assert stats["totalInteractions"] == 0
        assert stats["totalCost"] == 0.0
