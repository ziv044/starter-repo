"""Token budget management for context limits.

Tracks token usage and enforces budgets to prevent context overflow
and control costs.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pm6.cost")


# Approximate model context limits
MODEL_CONTEXT_LIMITS = {
    "claude-haiku-3-20240307": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4-20250514": 200_000,
}

# Approximate tokens per character (rough estimate)
CHARS_PER_TOKEN = 4


@dataclass
class TokenBudget:
    """Token budget configuration.

    Attributes:
        maxInputTokens: Maximum input tokens per request.
        maxOutputTokens: Maximum output tokens per request.
        maxTotalTokens: Maximum total tokens per session.
        warningThreshold: Percentage at which to warn (0.0-1.0).
        reserveTokens: Tokens to reserve for system prompt and response.
    """

    maxInputTokens: int = 100_000
    maxOutputTokens: int = 4_096
    maxTotalTokens: int = 500_000
    warningThreshold: float = 0.8
    reserveTokens: int = 10_000


@dataclass
class TokenUsage:
    """Current token usage tracking.

    Attributes:
        inputTokens: Total input tokens used.
        outputTokens: Total output tokens used.
        interactions: Number of interactions.
    """

    inputTokens: int = 0
    outputTokens: int = 0
    interactions: int = 0

    @property
    def totalTokens(self) -> int:
        """Get total tokens used."""
        return self.inputTokens + self.outputTokens


class TokenBudgetManager:
    """Manages token budgets for a simulation.

    Tracks usage, enforces limits, and triggers compaction when needed.

    Args:
        budget: Token budget configuration.
        model: Model name for context limit lookup.
    """

    def __init__(
        self,
        budget: TokenBudget | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        self._budget = budget or TokenBudget()
        self._model = model
        self._usage = TokenUsage()
        self._contextLimit = MODEL_CONTEXT_LIMITS.get(model, 200_000)

    def estimateTokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate.

        Returns:
            Estimated token count.
        """
        return len(text) // CHARS_PER_TOKEN

    def estimateMessagesTokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate tokens for a list of messages.

        Args:
            messages: List of message dicts with 'content' field.

        Returns:
            Estimated total tokens.
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimateTokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        total += self.estimateTokens(block["text"])
        return total

    def recordUsage(self, inputTokens: int, outputTokens: int) -> None:
        """Record token usage from an interaction.

        Args:
            inputTokens: Input tokens used.
            outputTokens: Output tokens used.
        """
        self._usage.inputTokens += inputTokens
        self._usage.outputTokens += outputTokens
        self._usage.interactions += 1

        logger.debug(
            f"Token usage: +{inputTokens}/{outputTokens}, "
            f"total={self._usage.totalTokens}"
        )

    def checkBudget(self, estimatedInput: int) -> dict[str, Any]:
        """Check if an interaction would exceed budget.

        Args:
            estimatedInput: Estimated input tokens for next interaction.

        Returns:
            Dict with 'allowed', 'warning', 'needsCompaction' flags.
        """
        result = {
            "allowed": True,
            "warning": False,
            "needsCompaction": False,
            "reason": None,
            "usage": self.getUsage(),
        }

        # Check per-request limit
        if estimatedInput > self._budget.maxInputTokens:
            result["allowed"] = False
            result["needsCompaction"] = True
            result["reason"] = (
                f"Input tokens ({estimatedInput}) exceed "
                f"max ({self._budget.maxInputTokens})"
            )
            return result

        # Check context limit
        if estimatedInput > self._contextLimit - self._budget.reserveTokens:
            result["allowed"] = False
            result["needsCompaction"] = True
            result["reason"] = (
                f"Would exceed context limit ({self._contextLimit})"
            )
            return result

        # Check session total
        projectedTotal = self._usage.totalTokens + estimatedInput
        if projectedTotal > self._budget.maxTotalTokens:
            result["allowed"] = False
            result["reason"] = (
                f"Would exceed session budget ({self._budget.maxTotalTokens})"
            )
            return result

        # Check warning threshold
        usageRatio = projectedTotal / self._budget.maxTotalTokens
        if usageRatio >= self._budget.warningThreshold:
            result["warning"] = True
            result["reason"] = (
                f"Approaching budget limit ({usageRatio:.0%} used)"
            )

        return result

    def getUsage(self) -> dict[str, Any]:
        """Get current usage statistics.

        Returns:
            Dict with usage stats.
        """
        return {
            "inputTokens": self._usage.inputTokens,
            "outputTokens": self._usage.outputTokens,
            "totalTokens": self._usage.totalTokens,
            "interactions": self._usage.interactions,
            "budgetRemaining": self._budget.maxTotalTokens - self._usage.totalTokens,
            "budgetUsedPercent": round(
                self._usage.totalTokens / self._budget.maxTotalTokens * 100, 1
            ),
        }

    def getRemainingBudget(self) -> int:
        """Get remaining token budget.

        Returns:
            Remaining tokens in budget.
        """
        return max(0, self._budget.maxTotalTokens - self._usage.totalTokens)

    def reset(self) -> None:
        """Reset usage tracking."""
        self._usage = TokenUsage()
        logger.info("Token budget reset")

    def setBudget(self, budget: TokenBudget) -> None:
        """Update the budget configuration.

        Args:
            budget: New budget configuration.
        """
        self._budget = budget

    def suggestCompactionLevel(self, targetReduction: float = 0.5) -> dict[str, Any]:
        """Suggest how much to compact based on current usage.

        Args:
            targetReduction: Target reduction ratio (0.0-1.0).

        Returns:
            Dict with compaction suggestions.
        """
        currentInput = self._usage.inputTokens
        targetTokens = int(currentInput * (1 - targetReduction))

        return {
            "currentInputTokens": currentInput,
            "targetInputTokens": targetTokens,
            "reductionNeeded": currentInput - targetTokens,
            "keepRecentMessages": max(3, int(10 * (1 - targetReduction))),
        }
