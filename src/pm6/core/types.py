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


# =============================================================================
# Pipeline / Orchestrator Types
# =============================================================================


class TurnMode(str, Enum):
    """Mode for executing turns."""

    INITIATIVE = "initiative"  # Legacy: agents roll for initiative
    ORCHESTRATOR = "orchestrator"  # New: orchestrator decides who acts


@dataclass
class PipelineStep:
    """A step in the turn pipeline.

    Attributes:
        step: Step identifier (e.g., 'turn_start', 'orchestrator_decide').
        config: Optional configuration for this step.
    """

    step: str
    config: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"step": self.step, "config": self.config}


@dataclass
class PipelineConfig:
    """Configuration for turn pipeline execution.

    Attributes:
        turnMode: How turns are executed (initiative or orchestrator).
        orchestratorName: Name of the orchestrator agent.
        orchestratorModel: Model to use for orchestrator (can be cheaper).
        steps: Ordered list of pipeline steps.
    """

    turnMode: TurnMode = TurnMode.ORCHESTRATOR
    orchestratorName: str = "orchestrator"
    orchestratorModel: str | None = None  # None = use agent's default
    steps: list[PipelineStep] = field(default_factory=list)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turnMode": self.turnMode.value,
            "orchestratorName": self.orchestratorName,
            "orchestratorModel": self.orchestratorModel,
            "steps": [s.toDict() for s in self.steps],
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "PipelineConfig":
        """Create from dictionary."""
        return cls(
            turnMode=TurnMode(data.get("turnMode", "orchestrator")),
            orchestratorName=data.get("orchestratorName", "orchestrator"),
            orchestratorModel=data.get("orchestratorModel"),
            steps=[
                PipelineStep(step=s.get("step", ""), config=s.get("config", {}))
                for s in data.get("steps", [])
            ],
        )

    @classmethod
    def default(cls) -> "PipelineConfig":
        """Create default orchestrator pipeline."""
        return cls(
            turnMode=TurnMode.ORCHESTRATOR,
            orchestratorName="orchestrator",
            steps=[
                PipelineStep(step="turn_start"),
                PipelineStep(step="gather_events"),
                PipelineStep(step="orchestrator_decide"),
                PipelineStep(step="execute_agents"),
                PipelineStep(step="player_turn"),
            ],
        )


@dataclass
class OrchestratorDecision:
    """Decision from the orchestrator about which agents should act.

    Attributes:
        agentsToWake: List of agent names that should act this turn.
        instructions: Optional specific instructions per agent.
        reasoning: Orchestrator's reasoning for the decision.
        skipPlayerTurn: Whether to skip the player turn.
    """

    agentsToWake: list[str] = field(default_factory=list)
    instructions: dict[str, str] = field(default_factory=dict)
    reasoning: str = ""
    skipPlayerTurn: bool = False

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agentsToWake": self.agentsToWake,
            "instructions": self.instructions,
            "reasoning": self.reasoning,
            "skipPlayerTurn": self.skipPlayerTurn,
        }


# =============================================================================
# Play Mode Types
# =============================================================================


class ResponseFormatType(str, Enum):
    """Types of response formats for player interaction."""

    MCQ = "mcq"  # Multiple choice (configurable count, default 4)
    YES_NO = "yes_no"  # Binary yes/no choice
    FREE_TEXT = "free_text"  # Free-form text input (requires LLM cycle)
    DYNAMIC = "dynamic"  # LLM decides based on context


@dataclass
class ResponseFormatConfig:
    """Configuration for player response format.

    Supports hierarchical override: Simulation -> Event -> Agent -> Dynamic.

    Attributes:
        formatType: Type of response format.
        choiceCount: Number of choices for MCQ format (default 4).
        showImpacts: Whether to show predicted impacts before selection.
        allowFormatOverride: Whether lower levels can override this config.
    """

    formatType: ResponseFormatType = ResponseFormatType.MCQ
    choiceCount: int = 4
    showImpacts: bool = True
    allowFormatOverride: bool = True

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "formatType": self.formatType.value,
            "choiceCount": self.choiceCount,
            "showImpacts": self.showImpacts,
            "allowFormatOverride": self.allowFormatOverride,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "ResponseFormatConfig":
        """Create from dictionary."""
        return cls(
            formatType=ResponseFormatType(data.get("formatType", "mcq")),
            choiceCount=data.get("choiceCount", 4),
            showImpacts=data.get("showImpacts", True),
            allowFormatOverride=data.get("allowFormatOverride", True),
        )


@dataclass
class Choice:
    """A choice presented to the player.

    Attributes:
        id: Unique identifier for this choice (e.g., "A", "B", "yes", "no").
        text: Display text for the choice.
        predictedImpacts: Pre-computed state changes if this choice is selected.
        source: Where this choice came from ("event", "agent", "system").
        agentName: If agent-generated, which agent suggested it.
    """

    id: str
    text: str
    predictedImpacts: dict[str, int | float] = field(default_factory=dict)
    source: str = "system"
    agentName: str | None = None

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "predictedImpacts": self.predictedImpacts,
            "source": self.source,
            "agentName": self.agentName,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "Choice":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            predictedImpacts=data.get("predictedImpacts", {}),
            source=data.get("source", "system"),
            agentName=data.get("agentName"),
        )


@dataclass
class StateChange:
    """A change to world state.

    Attributes:
        key: State key that changed.
        oldValue: Previous value.
        newValue: New value.
        delta: Numeric change (for numeric values).
        source: What caused the change.
    """

    key: str
    oldValue: Any
    newValue: Any
    delta: int | float | None = None
    source: str = "system"

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "oldValue": self.oldValue,
            "newValue": self.newValue,
            "delta": self.delta,
            "source": self.source,
        }


@dataclass
class PlayModeOutput:
    """Output for the Play Mode player view.

    Generated after agents respond, contains everything needed to render
    the player UI.

    Attributes:
        turnNumber: Current turn number.
        narrativeSummary: Human-readable summary of what happened.
        stateChanges: List of state changes that occurred.
        playerChoices: Available choices for the player.
        responseFormat: Format type for player response.
        agentResponses: Raw agent responses (for debugging/history).
        eventsTriggered: Events that fired this turn.
    """

    turnNumber: int
    narrativeSummary: str
    stateChanges: list[StateChange] = field(default_factory=list)
    playerChoices: list[Choice] = field(default_factory=list)
    responseFormat: ResponseFormatType = ResponseFormatType.MCQ
    agentResponses: list[AgentAction] = field(default_factory=list)
    eventsTriggered: list[Event] = field(default_factory=list)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turnNumber": self.turnNumber,
            "narrativeSummary": self.narrativeSummary,
            "stateChanges": [sc.toDict() for sc in self.stateChanges],
            "playerChoices": [c.toDict() for c in self.playerChoices],
            "responseFormat": self.responseFormat.value,
            "agentResponses": [ar.toDict() for ar in self.agentResponses],
            "eventsTriggered": [e.toDict() for e in self.eventsTriggered],
        }

    @property
    def hasChoices(self) -> bool:
        """Check if player has choices available."""
        return len(self.playerChoices) > 0

    @property
    def isMcq(self) -> bool:
        """Check if response format is multiple choice."""
        return self.responseFormat == ResponseFormatType.MCQ

    @property
    def isYesNo(self) -> bool:
        """Check if response format is yes/no."""
        return self.responseFormat == ResponseFormatType.YES_NO

    @property
    def isFreeText(self) -> bool:
        """Check if response format is free text."""
        return self.responseFormat == ResponseFormatType.FREE_TEXT


@dataclass
class PlayerInput:
    """Input from the player in response to PlayModeOutput.

    Attributes:
        choiceId: ID of selected choice (for MCQ/Yes-No).
        freeText: Free text input (for FREE_TEXT format).
        turnNumber: Turn this input is for.
        timestamp: When input was received.
    """

    choiceId: str | None = None
    freeText: str | None = None
    turnNumber: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "choiceId": self.choiceId,
            "freeText": self.freeText,
            "turnNumber": self.turnNumber,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def isFreeTextInput(self) -> bool:
        """Check if this is a free text input."""
        return self.freeText is not None and self.choiceId is None

    @property
    def isChoiceInput(self) -> bool:
        """Check if this is a choice selection."""
        return self.choiceId is not None


# =============================================================================
# Chief of Staff Mode Types
# =============================================================================


class PlayPhase(str, Enum):
    """Phases of play in Chief of Staff mode.

    The player cycles through these phases each turn:
    1. BRIEFING: CoS presents summarized intelligence from all agents
    2. MEETING: Optional free-text conversation with specific agent
    3. DECISION: Player makes strategic choice from available options
    """

    BRIEFING = "briefing"  # CoS presents agent summaries
    MEETING = "meeting"  # Player in direct conversation with agent
    DECISION = "decision"  # Player selecting strategic action


@dataclass
class AgentBrief:
    """A brief summary of an agent's position/recommendation.

    Used by Chief of Staff to summarize each agent's stance.

    Attributes:
        agentName: Name of the agent.
        agentRole: Agent's role/title.
        summary: 1-2 sentence summary of their position.
        recommendation: Their key recommendation.
        urgency: Urgency level (low, medium, high, critical).
        meetable: Whether player can request meeting with this agent.
    """

    agentName: str
    agentRole: str
    summary: str
    recommendation: str = ""
    urgency: str = "medium"
    meetable: bool = True

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agentName": self.agentName,
            "agentRole": self.agentRole,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "urgency": self.urgency,
            "meetable": self.meetable,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "AgentBrief":
        """Create from dictionary."""
        return cls(
            agentName=data.get("agentName", ""),
            agentRole=data.get("agentRole", ""),
            summary=data.get("summary", ""),
            recommendation=data.get("recommendation", ""),
            urgency=data.get("urgency", "medium"),
            meetable=data.get("meetable", True),
        )


@dataclass
class MeetingMessage:
    """A message in a meeting conversation.

    Attributes:
        role: 'player' or 'agent'.
        content: Message content.
        timestamp: When the message was sent.
    """

    role: str  # 'player' or 'agent'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MeetingState:
    """State of an active meeting with an agent.

    Attributes:
        agentName: Name of agent in meeting.
        agentRole: Agent's role/title.
        history: Conversation history.
        startTime: When meeting started.
        hoursSpent: Hours spent in this meeting.
    """

    agentName: str
    agentRole: str
    history: list[MeetingMessage] = field(default_factory=list)
    startTime: datetime = field(default_factory=datetime.now)
    hoursSpent: int = 0

    def addMessage(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.history.append(MeetingMessage(role=role, content=content))

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agentName": self.agentName,
            "agentRole": self.agentRole,
            "history": [m.toDict() for m in self.history],
            "startTime": self.startTime.isoformat(),
            "hoursSpent": self.hoursSpent,
        }


@dataclass
class CosBriefingOutput:
    """Output from Chief of Staff briefing phase.

    Attributes:
        turnNumber: Current turn number.
        gameTime: Current game time (datetime string).
        hoursElapsed: Hours elapsed this turn from meetings.
        eventSummary: Summary of events that triggered this briefing.
        agentBriefs: List of agent summaries.
        meetableAgents: Names of agents available for meeting.
        chiefOfStaffNarrative: CoS's opening narrative/framing.
        strategicChoices: Available strategic decisions (for decision phase).
    """

    turnNumber: int
    gameTime: str
    hoursElapsed: int = 0
    eventSummary: str = ""
    agentBriefs: list[AgentBrief] = field(default_factory=list)
    meetableAgents: list[str] = field(default_factory=list)
    chiefOfStaffNarrative: str = ""
    strategicChoices: list[Choice] = field(default_factory=list)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turnNumber": self.turnNumber,
            "gameTime": self.gameTime,
            "hoursElapsed": self.hoursElapsed,
            "eventSummary": self.eventSummary,
            "agentBriefs": [b.toDict() for b in self.agentBriefs],
            "meetableAgents": self.meetableAgents,
            "chiefOfStaffNarrative": self.chiefOfStaffNarrative,
            "strategicChoices": [c.toDict() for c in self.strategicChoices],
        }

    @property
    def hasMeetableAgents(self) -> bool:
        """Check if any agents are available for meeting."""
        return len(self.meetableAgents) > 0

    @property
    def hasStrategicChoices(self) -> bool:
        """Check if strategic choices are available."""
        return len(self.strategicChoices) > 0


@dataclass
class CosPlayState:
    """Current state of Chief of Staff play mode.

    Tracks the player's progress through the turn phases.

    Attributes:
        phase: Current phase (briefing, meeting, decision).
        currentBriefing: Active briefing output.
        currentMeeting: Active meeting state (if in meeting phase).
        totalHoursSpent: Total hours spent in meetings this turn.
        agentsMet: Names of agents already met this turn.
        turnStartTime: Game time at start of turn.
    """

    phase: PlayPhase = PlayPhase.BRIEFING
    currentBriefing: CosBriefingOutput | None = None
    currentMeeting: MeetingState | None = None
    totalHoursSpent: int = 0
    agentsMet: list[str] = field(default_factory=list)
    turnStartTime: str = ""

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase.value,
            "currentBriefing": self.currentBriefing.toDict() if self.currentBriefing else None,
            "currentMeeting": self.currentMeeting.toDict() if self.currentMeeting else None,
            "totalHoursSpent": self.totalHoursSpent,
            "agentsMet": self.agentsMet,
            "turnStartTime": self.turnStartTime,
        }

    def startMeeting(self, agentName: str, agentRole: str) -> None:
        """Start a meeting with an agent."""
        self.phase = PlayPhase.MEETING
        self.currentMeeting = MeetingState(agentName=agentName, agentRole=agentRole)

    def endMeeting(self, hoursSpent: int = 7) -> None:
        """End current meeting and return to briefing phase."""
        if self.currentMeeting:
            self.totalHoursSpent += hoursSpent
            self.agentsMet.append(self.currentMeeting.agentName)
            self.currentMeeting = None
        self.phase = PlayPhase.BRIEFING

    def proceedToDecision(self) -> None:
        """Move from briefing to decision phase."""
        self.phase = PlayPhase.DECISION

    def isInMeeting(self) -> bool:
        """Check if currently in a meeting."""
        return self.phase == PlayPhase.MEETING and self.currentMeeting is not None

    def isInBriefing(self) -> bool:
        """Check if currently in briefing phase."""
        return self.phase == PlayPhase.BRIEFING

    def isInDecision(self) -> bool:
        """Check if currently in decision phase."""
        return self.phase == PlayPhase.DECISION
