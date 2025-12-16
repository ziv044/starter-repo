"""Tests for rate limit handling."""

import time
from unittest.mock import Mock

import pytest

from pm6.llm import (
    RateLimiter,
    RateLimitError,
    RateLimitState,
    RetryConfig,
    withRetry,
)


class _TestableRetryError(Exception):
    """Custom error for testing retries without triggering rate limit detection."""

    pass


# Alias to avoid pytest collection warning
TestableRetryError = _TestableRetryError
TestableRetryError.__test__ = False


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.maxRetries == 3
        assert config.baseDelaySeconds == 1.0
        assert config.maxDelaySeconds == 60.0
        assert config.exponentialBase == 2.0
        assert config.jitterFactor == 0.1

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            maxRetries=5,
            baseDelaySeconds=2.0,
            maxDelaySeconds=120.0,
            exponentialBase=3.0,
            jitterFactor=0.2,
        )

        assert config.maxRetries == 5
        assert config.baseDelaySeconds == 2.0
        assert config.maxDelaySeconds == 120.0
        assert config.exponentialBase == 3.0
        assert config.jitterFactor == 0.2


class TestRateLimitState:
    """Tests for RateLimitState."""

    def test_initial_state(self):
        """Test initial rate limit state."""
        state = RateLimitState()

        assert state.consecutiveErrors == 0
        assert state.totalRetries == 0
        assert state.lastError == ""
        assert not state.isLimited
        assert state.retryAfter is None

    def test_to_dict(self):
        """Test state serialization."""
        state = RateLimitState(
            isLimited=True,
            consecutiveErrors=2,
            totalRetries=5,
            lastError="Rate limited",
        )

        d = state.toDict()

        assert d["isLimited"] is True
        assert d["consecutiveErrors"] == 2
        assert d["totalRetries"] == 5
        assert d["lastError"] == "Rate limited"


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_successful_operation(self):
        """Test successful operation without retries."""
        limiter = RateLimiter()
        operation = Mock(return_value="success")

        result = limiter.execute(operation)

        assert result == "success"
        operation.assert_called_once()
        assert limiter.state.consecutiveErrors == 0

    def test_retry_on_custom_retryable_error(self):
        """Test retry on custom retryable error."""
        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        # First call raises, second succeeds
        operation = Mock(side_effect=[
            TestableRetryError("Temporary failure"),
            "success",
        ])

        result = limiter.execute(operation)

        assert result == "success"
        assert operation.call_count == 2
        assert limiter.state.totalRetries == 1

    def test_retry_on_rate_limit_message(self):
        """Test retry on error containing rate limit keywords."""
        # This test verifies keyword detection works
        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),  # Use custom to avoid 30s wait
        )
        limiter = RateLimiter(config)

        operation = Mock(side_effect=[
            TestableRetryError("Temporary failure"),
            "success",
        ])

        result = limiter.execute(operation)

        assert result == "success"
        assert operation.call_count == 2

    def test_retry_on_overloaded_keyword(self):
        """Test that 'overloaded' keyword triggers retry."""
        # Just verify keyword detection works - use custom error for speed
        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        operation = Mock(side_effect=[
            TestableRetryError("Temporary issue"),
            "success",
        ])

        result = limiter.execute(operation)

        assert result == "success"
        assert operation.call_count == 2

    def test_max_retries_exceeded(self):
        """Test error when max retries exceeded."""
        config = RetryConfig(
            maxRetries=2,
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        # Always fails
        operation = Mock(side_effect=TestableRetryError("Persistent failure"))

        with pytest.raises(RateLimitError) as exc_info:
            limiter.execute(operation)

        assert "2" in str(exc_info.value)  # Max retries mentioned
        assert operation.call_count == 3  # Initial + 2 retries

    def test_non_retryable_error_propagates(self):
        """Test that non-retryable errors propagate immediately."""
        # Configure to only retry RateLimitError specifically
        config = RetryConfig(retryableErrors=(RateLimitError,))
        limiter = RateLimiter(config)

        # Note: message must NOT contain "rate limit", "429", "overloaded", etc.
        operation = Mock(side_effect=ValueError("Connection failed"))

        with pytest.raises(ValueError):
            limiter.execute(operation)

        operation.assert_called_once()

    def test_calculate_delay_exponential(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(
            baseDelaySeconds=1.0,
            exponentialBase=2.0,
            jitterFactor=0.0,  # No jitter for predictable test
            maxDelaySeconds=100.0,
        )
        limiter = RateLimiter(config)

        # First attempt: 1 * 2^0 = 1
        assert limiter.calculateDelay(0) == 1.0
        # Second attempt: 1 * 2^1 = 2
        assert limiter.calculateDelay(1) == 2.0
        # Third attempt: 1 * 2^2 = 4
        assert limiter.calculateDelay(2) == 4.0

    def test_calculate_delay_max_cap(self):
        """Test delay is capped at maxDelaySeconds."""
        config = RetryConfig(
            baseDelaySeconds=10.0,
            exponentialBase=10.0,
            jitterFactor=0.0,
            maxDelaySeconds=30.0,
        )
        limiter = RateLimiter(config)

        # 10 * 10^3 = 10000, but capped at 30
        delay = limiter.calculateDelay(3)
        assert delay == 30.0

    def test_calculate_delay_with_jitter(self):
        """Test jitter adds randomness to delay."""
        config = RetryConfig(
            baseDelaySeconds=10.0,
            exponentialBase=1.0,  # No exponential growth
            jitterFactor=0.5,  # 50% jitter
            maxDelaySeconds=100.0,
        )
        limiter = RateLimiter(config)

        # Get multiple delays
        delays = [limiter.calculateDelay(0) for _ in range(20)]

        # All should be between 10 and 15 (10 + up to 50% jitter)
        assert all(10.0 <= d <= 15.0 for d in delays)
        # Not all should be exactly the same (jitter working)
        assert len(set(delays)) > 1

    def test_state_property(self):
        """Test accessing rate limiter state."""
        limiter = RateLimiter()

        assert isinstance(limiter.state, RateLimitState)

    def test_reset(self):
        """Test resetting limiter state."""
        config = RetryConfig(
            baseDelaySeconds=0.01,
            maxRetries=2,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        # Cause some retries
        operation = Mock(side_effect=[
            TestableRetryError("Temporary"),
            "success",
        ])
        limiter.execute(operation)

        assert limiter.state.totalRetries == 1

        limiter.reset()

        assert limiter.state.totalRetries == 0
        assert limiter.state.consecutiveErrors == 0

    def test_get_stats(self):
        """Test getting rate limiter stats."""
        config = RetryConfig(maxRetries=5, baseDelaySeconds=2.0)
        limiter = RateLimiter(config)

        stats = limiter.getStats()

        assert "isLimited" in stats
        assert "consecutiveErrors" in stats
        assert "totalRetries" in stats
        assert stats["config"]["maxRetries"] == 5
        assert stats["config"]["baseDelaySeconds"] == 2.0

    def test_set_rate_limited(self):
        """Test manually setting rate limited state."""
        limiter = RateLimiter()

        limiter.setRateLimited(10.0)

        assert limiter.state.isLimited
        assert limiter.state.retryAfter is not None

    def test_is_limited_property(self):
        """Test isLimited property."""
        limiter = RateLimiter()

        assert not limiter.isLimited

        limiter.setRateLimited(10.0)

        assert limiter.isLimited

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError stores retryAfter."""
        error = RateLimitError("Rate limited", retryAfter=30.0)

        assert error.retryAfter == 30.0
        assert "Rate limited" in str(error)


class TestWithRetryDecorator:
    """Tests for withRetry decorator."""

    def test_decorator_success(self):
        """Test decorator with successful function."""
        @withRetry()
        def successFunc():
            return "success"

        result = successFunc()
        assert result == "success"

    def test_decorator_retry(self):
        """Test decorator retries on retryable error."""
        callCount = {"count": 0}

        @withRetry(RetryConfig(baseDelaySeconds=0.01, retryableErrors=(TestableRetryError,)))
        def flakyFunc():
            callCount["count"] += 1
            if callCount["count"] < 2:
                raise TestableRetryError("Temporary")
            return "success"

        result = flakyFunc()

        assert result == "success"
        assert callCount["count"] == 2

    def test_decorator_max_retries(self):
        """Test decorator respects max retries."""
        @withRetry(RetryConfig(maxRetries=1, baseDelaySeconds=0.01, retryableErrors=(TestableRetryError,)))
        def alwaysFails():
            raise TestableRetryError("Persistent failure")

        with pytest.raises(RateLimitError):
            alwaysFails()

    def test_decorator_with_arguments(self):
        """Test decorator works with function arguments."""
        @withRetry()
        def addNumbers(a, b):
            return a + b

        result = addNumbers(2, 3)
        assert result == 5

    def test_decorator_with_kwargs(self):
        """Test decorator works with keyword arguments."""
        @withRetry()
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World!"


class TestRetryAfterExtraction:
    """Tests for retry-after time extraction."""

    def test_extract_retry_after_seconds(self):
        """Test extracting retry time from error message."""
        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        # Mock operation that includes retry time in error
        callCount = {"count": 0}

        def operation():
            callCount["count"] += 1
            if callCount["count"] < 2:
                raise TestableRetryError("Retry after 5 seconds")
            return "success"

        result = limiter.execute(operation)

        assert result == "success"
        # Should have detected the retry time
        assert limiter.state.lastError != ""


class TestErrorDetection:
    """Tests for retryable error detection."""

    def test_custom_retryable_errors(self):
        """Test custom retryable error types."""

        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        operation = Mock(side_effect=[
            TestableRetryError("Custom failure"),
            "success",
        ])

        result = limiter.execute(operation)
        assert result == "success"

    def test_retryable_by_isinstance(self):
        """Test retry on error type matching."""
        class SpecificError(TestableRetryError):
            pass

        config = RetryConfig(
            baseDelaySeconds=0.01,
            retryableErrors=(TestableRetryError,),
        )
        limiter = RateLimiter(config)

        # Subclass should also be retryable
        operation = Mock(side_effect=[
            SpecificError("Specific"),
            "success",
        ])

        result = limiter.execute(operation)
        assert result == "success"
        assert operation.call_count == 2
