"""Cost estimation for operations.

Provides cost estimates before executing expensive operations,
enabling informed decisions about resource usage.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("pm6.cost")


# Pricing per 1M tokens (as of 2024)
MODEL_PRICING = {
    "claude-haiku-3-20240307": {"input": 0.25, "output": 1.25},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
}

# Average tokens per interaction (for rough estimates)
DEFAULT_INPUT_TOKENS = 500
DEFAULT_OUTPUT_TOKENS = 200
DEFAULT_SYSTEM_PROMPT_TOKENS = 300


@dataclass
class CostEstimate:
    """Estimated cost for an operation.

    Attributes:
        estimatedCost: Estimated cost in USD.
        minCost: Minimum expected cost.
        maxCost: Maximum expected cost.
        inputTokens: Estimated input tokens.
        outputTokens: Estimated output tokens.
        model: Model used for estimate.
        interactions: Number of interactions.
        cacheHitRate: Expected cache hit rate.
        details: Additional estimation details.
    """

    estimatedCost: float
    minCost: float = 0.0
    maxCost: float = 0.0
    inputTokens: int = 0
    outputTokens: int = 0
    model: str = "claude-sonnet-4-20250514"
    interactions: int = 1
    cacheHitRate: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def costRange(self) -> str:
        """Get formatted cost range string."""
        if self.minCost == self.maxCost:
            return f"${self.estimatedCost:.4f}"
        return f"${self.minCost:.4f} - ${self.maxCost:.4f}"

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimatedCost": round(self.estimatedCost, 6),
            "minCost": round(self.minCost, 6),
            "maxCost": round(self.maxCost, 6),
            "inputTokens": self.inputTokens,
            "outputTokens": self.outputTokens,
            "model": self.model,
            "interactions": self.interactions,
            "cacheHitRate": self.cacheHitRate,
            "costRange": self.costRange,
            "details": self.details,
        }


class CostEstimator:
    """Estimates costs for simulation operations.

    Provides upfront cost estimates to enable informed decisions.

    Args:
        defaultModel: Default model for estimates.
        cacheHitRate: Expected cache hit rate (0.0 to 1.0).
    """

    def __init__(
        self,
        defaultModel: str = "claude-sonnet-4-20250514",
        cacheHitRate: float = 0.0,
    ):
        self._defaultModel = defaultModel
        self._cacheHitRate = cacheHitRate
        self._tokenEstimates: dict[str, dict[str, int]] = {}

    def setDefaultModel(self, model: str) -> None:
        """Set the default model for estimates."""
        self._defaultModel = model

    def setCacheHitRate(self, rate: float) -> None:
        """Set the expected cache hit rate."""
        self._cacheHitRate = max(0.0, min(1.0, rate))

    def setTokenEstimates(
        self,
        agentName: str,
        inputTokens: int = DEFAULT_INPUT_TOKENS,
        outputTokens: int = DEFAULT_OUTPUT_TOKENS,
        systemPromptTokens: int = DEFAULT_SYSTEM_PROMPT_TOKENS,
    ) -> None:
        """Set token estimates for a specific agent.

        Args:
            agentName: Agent name.
            inputTokens: Expected input tokens per interaction.
            outputTokens: Expected output tokens per interaction.
            systemPromptTokens: Tokens in system prompt.
        """
        self._tokenEstimates[agentName] = {
            "input": inputTokens,
            "output": outputTokens,
            "systemPrompt": systemPromptTokens,
        }

    def getModelPricing(self, model: str | None = None) -> dict[str, float]:
        """Get pricing for a model.

        Args:
            model: Model name (None for default).

        Returns:
            Dict with input and output pricing per 1M tokens.
        """
        model = model or self._defaultModel
        return MODEL_PRICING.get(model, MODEL_PRICING[self._defaultModel])

    def estimateInteraction(
        self,
        inputText: str | None = None,
        agentName: str | None = None,
        model: str | None = None,
        systemPromptLength: int | None = None,
    ) -> CostEstimate:
        """Estimate cost for a single interaction.

        Args:
            inputText: User input text (for token estimation).
            agentName: Agent name (for saved estimates).
            model: Model to use.
            systemPromptLength: System prompt character length.

        Returns:
            CostEstimate for the interaction.
        """
        model = model or self._defaultModel
        pricing = self.getModelPricing(model)

        # Get token estimates
        if agentName and agentName in self._tokenEstimates:
            estimates = self._tokenEstimates[agentName]
            inputTokens = estimates["input"]
            outputTokens = estimates["output"]
            systemPromptTokens = estimates["systemPrompt"]
        else:
            inputTokens = DEFAULT_INPUT_TOKENS
            outputTokens = DEFAULT_OUTPUT_TOKENS
            systemPromptTokens = DEFAULT_SYSTEM_PROMPT_TOKENS

        # Adjust input tokens based on actual text
        if inputText:
            # Rough estimate: ~4 chars per token
            inputTokens = max(inputTokens, len(inputText) // 4)

        if systemPromptLength:
            systemPromptTokens = systemPromptLength // 4

        totalInput = inputTokens + systemPromptTokens
        inputCost = (totalInput / 1_000_000) * pricing["input"]
        outputCost = (outputTokens / 1_000_000) * pricing["output"]

        estimatedCost = inputCost + outputCost

        # Account for cache hit rate
        if self._cacheHitRate > 0:
            estimatedCost *= (1 - self._cacheHitRate)

        return CostEstimate(
            estimatedCost=estimatedCost,
            minCost=estimatedCost * 0.5,  # Minimum with good caching
            maxCost=estimatedCost * 2.0,  # Maximum with long responses
            inputTokens=totalInput,
            outputTokens=outputTokens,
            model=model,
            interactions=1,
            cacheHitRate=self._cacheHitRate,
            details={
                "userInputTokens": inputTokens,
                "systemPromptTokens": systemPromptTokens,
                "inputCost": inputCost,
                "outputCost": outputCost,
            },
        )

    def estimateBatch(
        self,
        count: int,
        agentName: str | None = None,
        model: str | None = None,
    ) -> CostEstimate:
        """Estimate cost for multiple interactions.

        Args:
            count: Number of interactions.
            agentName: Agent name.
            model: Model to use.

        Returns:
            CostEstimate for the batch.
        """
        single = self.estimateInteraction(agentName=agentName, model=model)

        # Apply cache hit rate to batch
        effectiveCount = count * (1 - self._cacheHitRate)

        return CostEstimate(
            estimatedCost=single.estimatedCost * effectiveCount,
            minCost=single.minCost * count * 0.3,  # Best case with caching
            maxCost=single.maxCost * count,
            inputTokens=single.inputTokens * count,
            outputTokens=single.outputTokens * count,
            model=single.model,
            interactions=count,
            cacheHitRate=self._cacheHitRate,
            details={
                "perInteractionCost": single.estimatedCost,
                "effectiveInteractions": effectiveCount,
            },
        )

    def estimateSession(
        self,
        turns: int,
        agentCount: int = 1,
        model: str | None = None,
    ) -> CostEstimate:
        """Estimate cost for a simulation session.

        Args:
            turns: Number of turns in the session.
            agentCount: Number of agents that might respond.
            model: Model to use.

        Returns:
            CostEstimate for the session.
        """
        # Estimate interactions per turn (usually 1, but could be more)
        interactionsPerTurn = min(agentCount, 2)  # Usually 1-2 agents respond
        totalInteractions = turns * interactionsPerTurn

        estimate = self.estimateBatch(totalInteractions, model=model)
        estimate.details["turns"] = turns
        estimate.details["agentCount"] = agentCount
        estimate.details["interactionsPerTurn"] = interactionsPerTurn

        return estimate

    def estimateReplay(
        self,
        sessionData: dict[str, Any],
        model: str | None = None,
    ) -> CostEstimate:
        """Estimate cost to replay a session (for testing variations).

        Args:
            sessionData: Session data from recorder.
            model: Model to use (None to use original).

        Returns:
            CostEstimate for replay.
        """
        interactions = sessionData.get("interactions", [])
        count = len(interactions)

        if count == 0:
            return CostEstimate(estimatedCost=0.0)

        # Calculate based on actual token usage if available
        totalInput = 0
        totalOutput = 0
        hasUsageData = False

        for interaction in interactions:
            usage = interaction.get("usage", {})
            if usage:
                hasUsageData = True
                totalInput += usage.get("inputTokens", 0)
                totalOutput += usage.get("outputTokens", 0)

        if hasUsageData:
            model = model or interactions[0].get("model", self._defaultModel)
            pricing = self.getModelPricing(model)

            inputCost = (totalInput / 1_000_000) * pricing["input"]
            outputCost = (totalOutput / 1_000_000) * pricing["output"]

            return CostEstimate(
                estimatedCost=inputCost + outputCost,
                minCost=(inputCost + outputCost) * 0.5,
                maxCost=(inputCost + outputCost) * 1.5,
                inputTokens=totalInput,
                outputTokens=totalOutput,
                model=model,
                interactions=count,
                cacheHitRate=0.0,  # Replay won't use cache
                details={
                    "fromActualUsage": True,
                    "inputCost": inputCost,
                    "outputCost": outputCost,
                },
            )

        # Fall back to estimation
        return self.estimateBatch(count, model=model)

    def willExceedLimit(
        self,
        estimate: CostEstimate,
        limit: float,
        currentCost: float = 0.0,
    ) -> bool:
        """Check if an estimate would exceed a cost limit.

        Args:
            estimate: Cost estimate.
            limit: Maximum allowed cost.
            currentCost: Cost already incurred.

        Returns:
            True if limit would be exceeded.
        """
        return (currentCost + estimate.estimatedCost) > limit

    def getRemainingBudget(
        self,
        limit: float,
        currentCost: float,
    ) -> dict[str, Any]:
        """Get remaining budget information.

        Args:
            limit: Maximum allowed cost.
            currentCost: Cost already incurred.

        Returns:
            Budget information dict.
        """
        remaining = max(0, limit - currentCost)
        pctUsed = (currentCost / limit * 100) if limit > 0 else 0

        # Estimate remaining interactions
        singleCost = self.estimateInteraction().estimatedCost
        remainingInteractions = int(remaining / singleCost) if singleCost > 0 else 0

        return {
            "limit": limit,
            "current": currentCost,
            "remaining": remaining,
            "percentUsed": round(pctUsed, 1),
            "estimatedRemainingInteractions": remainingInteractions,
            "warning": pctUsed > 80,
            "critical": pctUsed > 95,
        }

    def formatEstimate(self, estimate: CostEstimate) -> str:
        """Format an estimate as a human-readable string.

        Args:
            estimate: Cost estimate.

        Returns:
            Formatted string.
        """
        lines = [
            f"Cost Estimate: {estimate.costRange}",
            f"  Model: {estimate.model}",
            f"  Interactions: {estimate.interactions}",
            f"  Input tokens: ~{estimate.inputTokens:,}",
            f"  Output tokens: ~{estimate.outputTokens:,}",
        ]
        if estimate.cacheHitRate > 0:
            lines.append(f"  Expected cache hit rate: {estimate.cacheHitRate:.0%}")
        return "\n".join(lines)
