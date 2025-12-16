"""Anthropic API client with prompt caching and cost tracking.

Provides a wrapper around the Anthropic API with:
- Prompt caching using cache_control
- Automatic cost tracking
- Model routing integration
- Rate limit handling with exponential backoff
"""

import logging
from typing import Any

from anthropic import Anthropic

from pm6.config import getSettings
from pm6.cost.costTracker import CostTracker
from pm6.cost.modelRouter import ModelRouter, TaskType
from pm6.llm.rateLimiter import RateLimiter, RetryConfig

logger = logging.getLogger("pm6.llm")


class AnthropicClient:
    """Wrapper for Anthropic API with caching and cost tracking.

    Args:
        costTracker: Optional cost tracker for usage metrics.
        modelRouter: Optional model router for task-based routing.
        apiKey: Optional API key (defaults to settings).
        retryConfig: Optional retry configuration for rate limiting.
        enableRetry: Whether to enable automatic retry (default True).
    """

    def __init__(
        self,
        costTracker: CostTracker | None = None,
        modelRouter: ModelRouter | None = None,
        apiKey: str | None = None,
        retryConfig: RetryConfig | None = None,
        enableRetry: bool = True,
    ):
        settings = getSettings()
        self._client = Anthropic(api_key=apiKey or settings.anthropicApiKey)
        self._costTracker = costTracker
        self._modelRouter = modelRouter or ModelRouter()
        self._defaultModel = settings.defaultModel
        self._enableRetry = enableRetry
        self._rateLimiter = RateLimiter(retryConfig) if enableRetry else None

    def createMessage(
        self,
        messages: list[dict[str, Any]],
        systemPrompt: str | None = None,
        model: str | None = None,
        taskType: TaskType | None = None,
        maxTokens: int = 4096,
        temperature: float = 1.0,
        enableCache: bool = True,
    ) -> dict[str, Any]:
        """Create a message using the Anthropic API.

        Args:
            messages: Conversation messages.
            systemPrompt: System prompt with agent personality.
            model: Model to use (overrides taskType routing).
            taskType: Task type for model routing.
            maxTokens: Maximum response tokens.
            temperature: Sampling temperature.
            enableCache: Whether to enable prompt caching.

        Returns:
            Response dictionary with content and usage.
        """
        # Determine model
        if model is None:
            if taskType is not None:
                model = self._modelRouter.getModel(taskType)
            else:
                model = self._defaultModel

        # Build request
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": maxTokens,
            "temperature": temperature,
            "messages": messages,
        }

        # Add system prompt with caching
        if systemPrompt:
            if enableCache:
                request["system"] = [
                    {
                        "type": "text",
                        "text": systemPrompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                request["system"] = systemPrompt

        logger.debug(f"Calling {model} with {len(messages)} messages")

        # Make API call with optional retry
        if self._rateLimiter:
            response = self._rateLimiter.execute(
                lambda: self._client.messages.create(**request)
            )
        else:
            response = self._client.messages.create(**request)

        # Extract content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # Track costs if tracker available
        if self._costTracker:
            cachedTokens = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            self._costTracker.recordInteraction(
                model=model,
                inputTokens=response.usage.input_tokens,
                outputTokens=response.usage.output_tokens,
                cachedTokens=cachedTokens,
            )

        return {
            "content": content,
            "model": model,
            "usage": {
                "inputTokens": response.usage.input_tokens,
                "outputTokens": response.usage.output_tokens,
                "cachedTokens": getattr(response.usage, "cache_read_input_tokens", 0)
                or 0,
            },
            "stopReason": response.stop_reason,
        }

    def summarize(
        self,
        text: str,
        maxLength: int = 500,
    ) -> str:
        """Summarize text using Haiku for cost efficiency.

        Args:
            text: Text to summarize.
            maxLength: Approximate max length of summary.

        Returns:
            Summarized text.
        """
        prompt = f"Summarize the following in approximately {maxLength} characters:\n\n{text}"

        response = self.createMessage(
            messages=[{"role": "user", "content": prompt}],
            taskType=TaskType.SUMMARIZATION,
            maxTokens=1024,
            temperature=0.3,
            enableCache=False,
        )

        return response["content"]

    def compact(
        self,
        messages: list[dict[str, Any]],
        keepRecent: int = 5,
    ) -> list[dict[str, Any]]:
        """Compact message history using summarization.

        Args:
            messages: Full message history.
            keepRecent: Number of recent messages to keep verbatim.

        Returns:
            Compacted message list.
        """
        if len(messages) <= keepRecent:
            return messages

        # Split into old and recent
        oldMessages = messages[:-keepRecent]
        recentMessages = messages[-keepRecent:]

        # Summarize old messages
        oldText = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in oldMessages
        )

        summary = self.summarize(oldText)

        # Create compacted history
        summaryMessage = {
            "role": "user",
            "content": f"[Previous conversation summary: {summary}]",
        }

        logger.info(
            f"Compacted {len(oldMessages)} messages into summary, keeping {keepRecent} recent"
        )

        return [summaryMessage] + recentMessages

    def generateAgentResponse(
        self,
        agentSystemPrompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate an agent response with optimal settings.

        Args:
            agentSystemPrompt: The agent's system prompt.
            messages: Conversation history.
            model: Optional model override.

        Returns:
            Response with content and metadata.
        """
        return self.createMessage(
            messages=messages,
            systemPrompt=agentSystemPrompt,
            model=model,
            taskType=TaskType.AGENT_RESPONSE,
            enableCache=True,
        )
