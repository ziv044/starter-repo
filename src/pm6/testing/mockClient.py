"""Mock Anthropic client for testing.

Provides a drop-in replacement for AnthropicClient that returns
predefined responses for deterministic testing.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from pm6.cost.costTracker import CostTracker
from pm6.cost.modelRouter import ModelRouter, TaskType

logger = logging.getLogger("pm6.testing")


@dataclass
class MockResponse:
    """A mock response to return from the client.

    Attributes:
        content: Response content text.
        model: Model that "generated" the response.
        inputTokens: Simulated input tokens.
        outputTokens: Simulated output tokens.
        stopReason: Stop reason for the response.
    """

    content: str
    model: str = "claude-sonnet-4-20250514"
    inputTokens: int = 100
    outputTokens: int = 50
    stopReason: str = "end_turn"

    def toDict(self) -> dict[str, Any]:
        """Convert to response dictionary format."""
        return {
            "content": self.content,
            "model": self.model,
            "usage": {
                "inputTokens": self.inputTokens,
                "outputTokens": self.outputTokens,
                "cachedTokens": 0,
            },
            "stopReason": self.stopReason,
        }


# Type for response handlers
MockResponseHandler = Callable[[list[dict[str, Any]], str | None], MockResponse]


class MockAnthropicClient:
    """Mock client for testing without API calls.

    Supports three modes:
    1. Static responses: Return the same response for all calls
    2. Response sequences: Return responses in order
    3. Custom handlers: Use callbacks to generate responses

    Args:
        costTracker: Optional cost tracker for usage metrics.
        modelRouter: Optional model router.
        defaultResponse: Default response when no handler matches.
    """

    def __init__(
        self,
        costTracker: CostTracker | None = None,
        modelRouter: ModelRouter | None = None,
        defaultResponse: str = "Mock response",
    ):
        self._costTracker = costTracker
        self._modelRouter = modelRouter or ModelRouter()
        self._defaultModel = "claude-sonnet-4-20250514"
        self._defaultResponse = defaultResponse

        # Response configuration
        self._staticResponse: MockResponse | None = None
        self._responseQueue: list[MockResponse] = []
        self._responseHandlers: dict[str, MockResponseHandler] = {}
        self._agentResponses: dict[str, list[MockResponse]] = {}

        # Tracking for assertions
        self._callHistory: list[dict[str, Any]] = []
        self._callCount = 0

    def setStaticResponse(self, response: MockResponse | str) -> None:
        """Set a static response for all calls.

        Args:
            response: Response to return (str or MockResponse).
        """
        if isinstance(response, str):
            response = MockResponse(content=response)
        self._staticResponse = response

    def addResponse(self, response: MockResponse | str) -> None:
        """Add a response to the queue.

        Responses are returned in order. Queue is FIFO.

        Args:
            response: Response to add (str or MockResponse).
        """
        if isinstance(response, str):
            response = MockResponse(content=response)
        self._responseQueue.append(response)

    def addResponses(self, responses: list[MockResponse | str]) -> None:
        """Add multiple responses to the queue.

        Args:
            responses: List of responses to add.
        """
        for r in responses:
            self.addResponse(r)

    def addAgentResponse(self, agentName: str, response: MockResponse | str) -> None:
        """Add a response for a specific agent.

        Args:
            agentName: Agent to respond to.
            response: Response for that agent.
        """
        if isinstance(response, str):
            response = MockResponse(content=response)
        if agentName not in self._agentResponses:
            self._agentResponses[agentName] = []
        self._agentResponses[agentName].append(response)

    def registerHandler(self, pattern: str, handler: MockResponseHandler) -> None:
        """Register a handler for specific patterns.

        Args:
            pattern: Pattern to match in user input.
            handler: Callback that generates response.
        """
        self._responseHandlers[pattern] = handler

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
        """Create a mock message response.

        Args:
            messages: Conversation messages.
            systemPrompt: System prompt.
            model: Model to use.
            taskType: Task type for routing.
            maxTokens: Maximum tokens.
            temperature: Sampling temperature.
            enableCache: Whether caching is enabled.

        Returns:
            Mock response dictionary.
        """
        # Determine model
        if model is None:
            if taskType is not None:
                model = self._modelRouter.getModel(taskType)
            else:
                model = self._defaultModel

        # Record call
        self._callHistory.append(
            {
                "messages": messages,
                "systemPrompt": systemPrompt,
                "model": model,
                "taskType": taskType,
                "maxTokens": maxTokens,
                "temperature": temperature,
            }
        )
        self._callCount += 1

        # Get last user message for pattern matching
        userMessage = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                userMessage = msg.get("content", "")
                break

        # Find response
        response = self._getResponse(messages, systemPrompt, userMessage)

        # Update model in response
        responseDict = response.toDict()
        responseDict["model"] = model

        # Track costs if tracker available
        if self._costTracker:
            self._costTracker.recordInteraction(
                model=model,
                inputTokens=response.inputTokens,
                outputTokens=response.outputTokens,
                cachedTokens=0,
            )

        logger.debug(f"Mock response generated: {response.content[:50]}...")
        return responseDict

    def _getResponse(
        self,
        messages: list[dict[str, Any]],
        systemPrompt: str | None,
        userMessage: str,
    ) -> MockResponse:
        """Determine which response to return.

        Args:
            messages: Conversation messages.
            systemPrompt: System prompt.
            userMessage: Last user message.

        Returns:
            MockResponse to return.
        """
        # Check handlers first
        for pattern, handler in self._responseHandlers.items():
            if pattern in userMessage:
                return handler(messages, systemPrompt)

        # Check response queue
        if self._responseQueue:
            return self._responseQueue.pop(0)

        # Check static response
        if self._staticResponse:
            return self._staticResponse

        # Default response
        return MockResponse(content=self._defaultResponse)

    def generateAgentResponse(
        self,
        agentSystemPrompt: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate a mock agent response.

        Args:
            agentSystemPrompt: Agent's system prompt.
            messages: Conversation history.
            model: Model override.

        Returns:
            Mock response dictionary.
        """
        # Try to extract agent name from system prompt for agent-specific responses
        agentName = self._extractAgentName(agentSystemPrompt)
        if agentName and agentName in self._agentResponses:
            responses = self._agentResponses[agentName]
            if responses:
                response = responses.pop(0)
                responseDict = response.toDict()
                responseDict["model"] = model or self._defaultModel

                self._callCount += 1
                self._callHistory.append(
                    {
                        "agentSystemPrompt": agentSystemPrompt,
                        "messages": messages,
                        "model": model,
                        "agentName": agentName,
                    }
                )

                if self._costTracker:
                    self._costTracker.recordInteraction(
                        model=model or self._defaultModel,
                        inputTokens=response.inputTokens,
                        outputTokens=response.outputTokens,
                        cachedTokens=0,
                    )

                return responseDict

        # Fall back to createMessage
        return self.createMessage(
            messages=messages,
            systemPrompt=agentSystemPrompt,
            model=model,
            taskType=TaskType.AGENT_RESPONSE,
        )

    def _extractAgentName(self, systemPrompt: str) -> str | None:
        """Try to extract agent name from system prompt.

        Simple heuristic - looks for "You are X" pattern.
        """
        if not systemPrompt:
            return None
        # Look for common patterns
        if "You are " in systemPrompt:
            parts = systemPrompt.split("You are ", 1)[1]
            name = parts.split()[0].strip(".,")
            return name
        return None

    def summarize(self, text: str, maxLength: int = 500) -> str:
        """Return a mock summary.

        Args:
            text: Text to summarize.
            maxLength: Max length.

        Returns:
            Mock summary.
        """
        # Simple mock: just truncate
        return f"[Summary: {text[:maxLength]}...]"

    def compact(
        self,
        messages: list[dict[str, Any]],
        keepRecent: int = 5,
    ) -> list[dict[str, Any]]:
        """Return compacted messages.

        Args:
            messages: Message history.
            keepRecent: Messages to keep.

        Returns:
            Compacted messages.
        """
        if len(messages) <= keepRecent:
            return messages

        recentMessages = messages[-keepRecent:]
        summaryMessage = {
            "role": "user",
            "content": f"[Previous conversation summary: {len(messages) - keepRecent} messages compacted]",
        }
        return [summaryMessage] + recentMessages

    # Assertion helpers

    @property
    def callCount(self) -> int:
        """Get the number of calls made."""
        return self._callCount

    @property
    def callHistory(self) -> list[dict[str, Any]]:
        """Get the full call history."""
        return self._callHistory.copy()

    def getLastCall(self) -> dict[str, Any] | None:
        """Get the last call made."""
        if not self._callHistory:
            return None
        return self._callHistory[-1]

    def wasCalledWith(self, content: str) -> bool:
        """Check if a call contained specific content.

        Args:
            content: Content to search for.

        Returns:
            True if content was found in any call.
        """
        for call in self._callHistory:
            messages = call.get("messages", [])
            for msg in messages:
                if content in msg.get("content", ""):
                    return True
        return False

    def reset(self) -> None:
        """Reset all state for fresh testing."""
        self._staticResponse = None
        self._responseQueue.clear()
        self._responseHandlers.clear()
        self._agentResponses.clear()
        self._callHistory.clear()
        self._callCount = 0


@dataclass
class TestScenario:
    """A test scenario with predefined interactions.

    Attributes:
        name: Scenario name.
        description: What the scenario tests.
        responses: Ordered list of responses.
        expectedCalls: Expected number of LLM calls.
        worldState: Initial world state.
    """

    name: str
    description: str = ""
    responses: list[MockResponse] = field(default_factory=list)
    expectedCalls: int = 0
    worldState: dict[str, Any] = field(default_factory=dict)

    def toClient(self) -> MockAnthropicClient:
        """Create a configured mock client for this scenario."""
        client = MockAnthropicClient()
        client.addResponses(self.responses)
        return client
