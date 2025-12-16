"""Response models for agent interactions.

Provides structured response types for simulation interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentResponse:
    """Response from an agent interaction.

    Attributes:
        agentName: Name of the responding agent.
        content: The response text content.
        timestamp: When the response was generated.
        fromCache: Whether response came from cache.
        model: Model used (if not cached).
        usage: Token usage (if not cached).
        metadata: Additional response metadata.
    """

    agentName: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    fromCache: bool = False
    model: str | None = None
    usage: dict[str, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agentName": self.agentName,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "fromCache": self.fromCache,
            "model": self.model,
            "usage": self.usage,
            "metadata": self.metadata,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "AgentResponse":
        """Create from dictionary."""
        return cls(
            agentName=data["agentName"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            fromCache=data.get("fromCache", False),
            model=data.get("model"),
            usage=data.get("usage"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class InteractionResult:
    """Result of a simulation interaction round.

    Attributes:
        responses: List of agent responses.
        worldStateChanges: Changes to world state.
        timestamp: When the interaction occurred.
    """

    responses: list[AgentResponse] = field(default_factory=list)
    worldStateChanges: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "responses": [r.toDict() for r in self.responses],
            "worldStateChanges": self.worldStateChanges,
            "timestamp": self.timestamp.isoformat(),
        }
