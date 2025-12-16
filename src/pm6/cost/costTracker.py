"""Cost tracking for LLM usage.

Tracks tokens, costs, and cache hit rates to enable
continuous optimization and visibility.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger("pm6.cost")


# Approximate pricing per 1M tokens (as of 2024)
MODEL_PRICING = {
    "claude-haiku-3-20240307": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}


@dataclass
class InteractionCost:
    """Cost data for a single interaction.

    Attributes:
        timestamp: When the interaction occurred.
        model: Model used.
        inputTokens: Number of input tokens.
        outputTokens: Number of output tokens.
        cachedTokens: Tokens served from prompt cache.
        cost: Estimated cost in USD.
        cacheHit: Whether response came from response cache.
    """

    timestamp: datetime
    model: str
    inputTokens: int
    outputTokens: int
    cachedTokens: int = 0
    cost: float = 0.0
    cacheHit: bool = False


@dataclass
class SessionStats:
    """Aggregated stats for a session.

    Attributes:
        totalInteractions: Number of interactions.
        totalInputTokens: Total input tokens.
        totalOutputTokens: Total output tokens.
        totalCachedTokens: Total tokens from prompt cache.
        totalCost: Total estimated cost.
        cacheHits: Number of response cache hits.
        cacheMisses: Number of response cache misses.
        startTime: Session start time.
        interactions: Individual interaction costs.
    """

    totalInteractions: int = 0
    totalInputTokens: int = 0
    totalOutputTokens: int = 0
    totalCachedTokens: int = 0
    totalCost: float = 0.0
    cacheHits: int = 0
    cacheMisses: int = 0
    startTime: datetime = field(default_factory=datetime.now)
    interactions: list[InteractionCost] = field(default_factory=list)


class CostTracker:
    """Tracks costs and usage metrics for a simulation.

    Provides visibility into LLM usage, cache efficiency,
    and estimated costs.
    """

    def __init__(self):
        self._stats = SessionStats()

    def recordInteraction(
        self,
        model: str,
        inputTokens: int,
        outputTokens: int,
        cachedTokens: int = 0,
        cacheHit: bool = False,
    ) -> InteractionCost:
        """Record an interaction's cost.

        Args:
            model: Model used for the interaction.
            inputTokens: Number of input tokens.
            outputTokens: Number of output tokens.
            cachedTokens: Tokens served from prompt cache.
            cacheHit: Whether response came from response cache.

        Returns:
            The recorded interaction cost.
        """
        # Calculate cost
        pricing = MODEL_PRICING.get(
            model,
            {"input": 3.0, "output": 15.0},  # Default to Sonnet pricing
        )

        # Cached tokens are discounted (90% reduction)
        effectiveInputTokens = inputTokens - (cachedTokens * 0.9)
        inputCost = (effectiveInputTokens / 1_000_000) * pricing["input"]
        outputCost = (outputTokens / 1_000_000) * pricing["output"]
        totalCost = inputCost + outputCost

        # Create interaction record
        interaction = InteractionCost(
            timestamp=datetime.now(),
            model=model,
            inputTokens=inputTokens,
            outputTokens=outputTokens,
            cachedTokens=cachedTokens,
            cost=totalCost,
            cacheHit=cacheHit,
        )

        # Update session stats
        self._stats.totalInteractions += 1
        self._stats.totalInputTokens += inputTokens
        self._stats.totalOutputTokens += outputTokens
        self._stats.totalCachedTokens += cachedTokens
        self._stats.totalCost += totalCost

        if cacheHit:
            self._stats.cacheHits += 1
        else:
            self._stats.cacheMisses += 1

        self._stats.interactions.append(interaction)

        logger.info(
            f"Interaction: model={model}, cost=${totalCost:.4f}, "
            f"tokens={inputTokens}+{outputTokens}, cached={cachedTokens}"
        )

        return interaction

    def recordCacheHit(self) -> None:
        """Record a response cache hit (no LLM call made)."""
        self._stats.cacheHits += 1
        self._stats.totalInteractions += 1
        logger.info("Response cache hit - no LLM call")

    def getStats(self) -> dict[str, Any]:
        """Get current session statistics.

        Returns:
            Dictionary with session stats.
        """
        totalRequests = self._stats.cacheHits + self._stats.cacheMisses
        cacheHitRate = (
            self._stats.cacheHits / totalRequests if totalRequests > 0 else 0.0
        )

        return {
            "totalInteractions": self._stats.totalInteractions,
            "totalInputTokens": self._stats.totalInputTokens,
            "totalOutputTokens": self._stats.totalOutputTokens,
            "totalCachedTokens": self._stats.totalCachedTokens,
            "totalCost": round(self._stats.totalCost, 4),
            "cacheHits": self._stats.cacheHits,
            "cacheMisses": self._stats.cacheMisses,
            "cacheHitRate": round(cacheHitRate, 3),
            "sessionDuration": (datetime.now() - self._stats.startTime).total_seconds(),
        }

    def getCostEstimate(self, inputTokens: int, outputTokens: int, model: str) -> float:
        """Estimate cost for a potential interaction.

        Args:
            inputTokens: Estimated input tokens.
            outputTokens: Estimated output tokens.
            model: Model to use.

        Returns:
            Estimated cost in USD.
        """
        pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
        inputCost = (inputTokens / 1_000_000) * pricing["input"]
        outputCost = (outputTokens / 1_000_000) * pricing["output"]
        return inputCost + outputCost

    def reset(self) -> None:
        """Reset all statistics."""
        self._stats = SessionStats()
        logger.info("Cost tracker reset")
