"""Type definitions for simulation engine.

Defines dataclasses for turn-based simulation mechanics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ActionType(Enum):
    """Types of actions an agent can take."""

    SPEAK = "speak"  # Agent says something
    ACT = "act"  # Agent performs an action
    REACT = "react"  # Agent reacts to something
    OBSERVE = "observe"  # Agent observes/notices something


@dataclass
class AgentAction:
    """An action taken by an agent during a turn.

    Attributes:
        agentName: Name of the agent taking the action.
        actionType: Type of action taken.
        content: The content of the action (speech, description, etc.).
        target: Optional target of the action (another agent, player, etc.).
        metadata: Additional action metadata.
        timestamp: When the action occurred.
    """

    agentName: str
    actionType: ActionType
    content: str
    target: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agentName": self.agentName,
            "actionType": self.actionType.value,
            "content": self.content,
            "target": self.target,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Event:
    """An event that occurred during the simulation.

    Attributes:
        name: Event name/type (e.g., 'turn_start', 'state_changed').
        data: Event payload data.
        source: What triggered the event (agent name, 'system', etc.).
        timestamp: When the event occurred.
    """

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ScheduledEvent:
    """An event scheduled to occur on a specific turn.

    Attributes:
        turn: Turn number when the event should fire.
        event: The event to fire.
        recurring: Whether the event should repeat.
        interval: Turns between recurrences (if recurring).
    """

    turn: int
    event: Event
    recurring: bool = False
    interval: int = 1


@dataclass
class TurnResult:
    """Result of executing a simulation turn.

    Attributes:
        turnNumber: The turn number that was executed.
        cpuActions: Actions taken by CPU agents during this turn.
        events: Events that fired during this turn.
        stateChanges: Changes to world state during this turn.
        playerPending: Whether player input is needed.
        playerPrompt: Prompt for player if input needed.
    """

    turnNumber: int
    cpuActions: list[AgentAction] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    stateChanges: dict[str, Any] = field(default_factory=dict)
    playerPending: bool = False
    playerPrompt: str | None = None

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turnNumber": self.turnNumber,
            "cpuActions": [a.toDict() for a in self.cpuActions],
            "events": [e.toDict() for e in self.events],
            "stateChanges": self.stateChanges,
            "playerPending": self.playerPending,
            "playerPrompt": self.playerPrompt,
        }

    @property
    def hasCpuActions(self) -> bool:
        """Check if any CPU agents took actions."""
        return len(self.cpuActions) > 0

    @property
    def hasEvents(self) -> bool:
        """Check if any events fired."""
        return len(self.events) > 0


@dataclass
class EngineState:
    """State of the simulation engine.

    Attributes:
        currentTurn: Current turn number.
        isRunning: Whether engine is actively running.
        isPaused: Whether engine is paused.
        lastTurnResult: Result of the last turn.
    """

    currentTurn: int = 0
    isRunning: bool = False
    isPaused: bool = False
    lastTurnResult: TurnResult | None = None
