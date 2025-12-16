"""Agent configuration using Pydantic models."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from pm6.agents.memoryPolicy import MemoryPolicy


class AgentConfig(BaseModel):
    """Configuration for a simulation agent.

    Agents are the characters/entities in a simulation that respond
    to user interactions with AI-generated responses.

    Attributes:
        name: Unique identifier for the agent.
        role: Description of the agent's role in the simulation.
        systemPrompt: The system prompt defining agent behavior.
        model: Claude model to use for this agent's responses.
        memoryPolicy: How the agent retains information.
        maxTurns: Turns before memory compaction (if using SUMMARY policy).
        situationTypes: Types of situations this agent handles.
        tools: Tool names this agent can use.
        controlledBy: Whether agent is controlled by 'player' or 'cpu'.
        initiative: Probability (0-1) that CPU agent speaks on a turn.
        metadata: Additional agent-specific data.
    """

    name: str = Field(
        ...,
        description="Unique identifier for the agent",
        min_length=1,
    )
    role: str = Field(
        ...,
        description="Description of the agent's role",
    )
    systemPrompt: str = Field(
        default="",
        description="System prompt defining agent behavior",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model for responses",
    )
    memoryPolicy: MemoryPolicy = Field(
        default=MemoryPolicy.SUMMARY,
        description="Memory retention policy",
    )
    maxTurns: int = Field(
        default=10,
        description="Turns before memory compaction",
        ge=1,
    )
    situationTypes: list[str] = Field(
        default_factory=list,
        description="Situation types this agent handles",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Tools this agent can use",
    )
    controlledBy: Literal["player", "cpu"] = Field(
        default="cpu",
        description="Whether agent is controlled by player or CPU",
    )
    initiative: float = Field(
        default=0.5,
        description="Probability (0-1) that CPU agent speaks on a turn",
        ge=0.0,
        le=1.0,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional agent-specific data",
    )

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the agent config.
        """
        return self.model_dump(mode="json")

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create from dictionary.

        Args:
            data: Dictionary with agent configuration.

        Returns:
            AgentConfig instance.
        """
        return cls.model_validate(data)

    @property
    def isPlayer(self) -> bool:
        """Check if this agent is controlled by the player."""
        return self.controlledBy == "player"

    @property
    def isCpu(self) -> bool:
        """Check if this agent is controlled by the CPU."""
        return self.controlledBy == "cpu"
