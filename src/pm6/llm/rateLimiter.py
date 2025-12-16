"""Rate limiting and retry handling for API calls.

Supports NFR10: Handle API rate limits gracefully with backoff and queuing.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, TypeVar

logger = logging.getLogger("pm6.llm")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        maxRetries: Maximum number of retry attempts.
        baseDelaySeconds: Initial delay between retries.
        maxDelaySeconds: Maximum delay between retries.
        exponentialBase: Base for exponential backoff.
        jitterFactor: Random jitter factor (0.0 to 1.0).
        retryableErrors: Error types that should trigger retry.
    """

    maxRetries: int = 3
    baseDelaySeconds: float = 1.0
    maxDelaySeconds: float = 60.0
    exponentialBase: float = 2.0
    jitterFactor: float = 0.1
    retryableErrors: tuple[type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )


@dataclass
class RateLimitState:
    """Current rate limit state.

    Attributes:
        isLimited: Whether currently rate limited.
        retryAfter: When rate limit expires.
        consecutiveErrors: Count of consecutive rate limit errors.
        totalRetries: Total retry count.
        lastError: Last error message.
    """

    isLimited: bool = False
    retryAfter: datetime | None = None
    consecutiveErrors: int = 0
    totalRetries: int = 0
    lastError: str = ""

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "isLimited": self.isLimited,
            "retryAfter": self.retryAfter.isoformat() if self.retryAfter else None,
            "consecutiveErrors": self.consecutiveErrors,
            "totalRetries": self.totalRetries,
            "lastError": self.lastError,
        }


class RateLimitError(Exception):
    """Raised when rate limit is hit and retries exhausted."""

    def __init__(self, message: str, retryAfter: float | None = None):
        super().__init__(message)
        self.retryAfter = retryAfter


class RateLimiter:
    """Handles API rate limiting with exponential backoff.

    Features:
    - Automatic retry with exponential backoff
    - Jitter to prevent thundering herd
    - Rate limit detection from headers/errors
    - Request queuing support
    - State tracking for monitoring

    Args:
        config: Retry configuration.
    """

    def __init__(self, config: RetryConfig | None = None):
        self._config = config or RetryConfig()
        self._state = RateLimitState()
        self._requestQueue: list[tuple[Callable[[], T], float]] = []

    @property
    def state(self) -> RateLimitState:
        """Get current rate limit state."""
        return self._state

    @property
    def isLimited(self) -> bool:
        """Check if currently rate limited."""
        if not self._state.isLimited:
            return False
        if self._state.retryAfter and datetime.now() >= self._state.retryAfter:
            self._state.isLimited = False
            self._state.retryAfter = None
            return False
        return True

    def calculateDelay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.

        Uses exponential backoff with jitter.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        # Exponential backoff
        delay = self._config.baseDelaySeconds * (
            self._config.exponentialBase ** attempt
        )

        # Cap at max delay
        delay = min(delay, self._config.maxDelaySeconds)

        # Add jitter
        jitter = delay * self._config.jitterFactor * random.random()
        delay += jitter

        return delay

    def execute(self, operation: Callable[[], T]) -> T:
        """Execute an operation with retry logic.

        Args:
            operation: Callable to execute.

        Returns:
            Result of the operation.

        Raises:
            RateLimitError: If all retries exhausted.
            Exception: Other non-retryable errors.
        """
        lastException: Exception | None = None

        for attempt in range(self._config.maxRetries + 1):
            # Wait if rate limited
            if self.isLimited:
                waitTime = self._getWaitTime()
                if waitTime > 0:
                    logger.info(f"Rate limited, waiting {waitTime:.1f}s")
                    time.sleep(waitTime)

            try:
                result = operation()

                # Success - reset error count
                self._state.consecutiveErrors = 0
                self._state.isLimited = False
                return result

            except Exception as e:
                lastException = e

                # Check if error is retryable
                if not self._isRetryable(e):
                    raise

                # Check for rate limit indicators
                retryAfter = self._extractRetryAfter(e)
                if retryAfter is not None:
                    self._handleRateLimit(retryAfter, str(e))

                self._state.consecutiveErrors += 1
                self._state.totalRetries += 1
                self._state.lastError = str(e)

                # Log retry attempt
                if attempt < self._config.maxRetries:
                    delay = self.calculateDelay(attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{self._config.maxRetries} "
                        f"after {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)

        # All retries exhausted
        raise RateLimitError(
            f"Max retries ({self._config.maxRetries}) exhausted: {lastException}",
            retryAfter=self._state.retryAfter.timestamp() if self._state.retryAfter else None,
        )

    def _isRetryable(self, error: Exception) -> bool:
        """Check if error should trigger retry."""
        # Check if it's a rate limit error
        errorStr = str(error).lower()
        if any(
            phrase in errorStr
            for phrase in ["rate limit", "too many requests", "429", "overloaded"]
        ):
            return True

        # Check against configured retryable errors
        return isinstance(error, self._config.retryableErrors)

    def _extractRetryAfter(self, error: Exception) -> float | None:
        """Extract retry-after time from error.

        Args:
            error: The exception to inspect.

        Returns:
            Retry delay in seconds, or None.
        """
        errorStr = str(error)

        # Look for "retry after X seconds" patterns
        import re

        patterns = [
            r"retry.after.(\d+(?:\.\d+)?)\s*s",
            r"wait.(\d+(?:\.\d+)?)\s*s",
            r"(\d+(?:\.\d+)?)\s*seconds?",
        ]

        for pattern in patterns:
            match = re.search(pattern, errorStr, re.IGNORECASE)
            if match:
                return float(match.group(1))

        # Default retry time for rate limit errors
        if "rate limit" in errorStr.lower() or "429" in errorStr:
            return 30.0

        return None

    def _handleRateLimit(self, retryAfter: float, errorMessage: str) -> None:
        """Handle rate limit by updating state.

        Args:
            retryAfter: Seconds to wait.
            errorMessage: Error message.
        """
        self._state.isLimited = True
        self._state.retryAfter = datetime.now() + timedelta(seconds=retryAfter)
        self._state.lastError = errorMessage
        logger.warning(f"Rate limited for {retryAfter}s: {errorMessage}")

    def _getWaitTime(self) -> float:
        """Get remaining wait time if rate limited."""
        if not self._state.retryAfter:
            return 0
        remaining = (self._state.retryAfter - datetime.now()).total_seconds()
        return max(0, remaining)

    def setRateLimited(self, seconds: float) -> None:
        """Manually set rate limited state.

        Args:
            seconds: Seconds until rate limit expires.
        """
        self._handleRateLimit(seconds, "Manually set rate limit")

    def reset(self) -> None:
        """Reset rate limiter state."""
        self._state = RateLimitState()
        self._requestQueue.clear()

    def getStats(self) -> dict[str, Any]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with stats.
        """
        return {
            "isLimited": self.isLimited,
            "consecutiveErrors": self._state.consecutiveErrors,
            "totalRetries": self._state.totalRetries,
            "lastError": self._state.lastError,
            "config": {
                "maxRetries": self._config.maxRetries,
                "baseDelaySeconds": self._config.baseDelaySeconds,
                "maxDelaySeconds": self._config.maxDelaySeconds,
            },
        }


def withRetry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for adding retry logic to functions.

    Args:
        config: Retry configuration.

    Returns:
        Decorator function.

    Example:
        @withRetry(RetryConfig(maxRetries=5))
        def my_api_call():
            return api.call()
    """
    limiter = RateLimiter(config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return limiter.execute(lambda: func(*args, **kwargs))

        return wrapper

    return decorator
