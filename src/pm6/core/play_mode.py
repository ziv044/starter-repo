"""Play Mode output generation for end-player experience.

Generates PlayModeOutput from agent responses and events, containing:
- Narrative summary of what happened
- State changes visualization
- Player choices with pre-computed impacts
"""

import logging
from typing import Any

from pm6.core.choice_generator import ChoiceGenerator
from pm6.core.types import (
    AgentAction,
    Choice,
    Event,
    PlayModeOutput,
    PlayerInput,
    ResponseFormatConfig,
    ResponseFormatType,
    StateChange,
)

logger = logging.getLogger("pm6.core.play_mode")


class PlayModeGenerator:
    """Generates Play Mode output for the player view.

    Takes raw simulation outputs (agent responses, events, state changes)
    and produces a player-friendly PlayModeOutput.
    """

    def __init__(self) -> None:
        """Initialize the Play Mode generator."""
        self._choiceGenerator = ChoiceGenerator()

    def generateOutput(
        self,
        turnNumber: int,
        agentResponses: list[AgentAction],
        events: list[Event],
        stateChanges: dict[str, tuple[Any, Any]],
        formatConfig: ResponseFormatConfig,
        worldState: dict[str, Any] | None = None,
    ) -> PlayModeOutput:
        """Generate Play Mode output from turn results.

        Args:
            turnNumber: Current turn number.
            agentResponses: Actions taken by agents this turn.
            events: Events that fired this turn.
            stateChanges: State changes as {key: (old_value, new_value)}.
            formatConfig: Response format configuration.
            worldState: Current world state for context.

        Returns:
            PlayModeOutput ready for rendering in player view.
        """
        # Generate narrative summary from agent responses
        narrative = self._generateNarrative(agentResponses, events)

        # Convert state changes to structured format
        stateChangeList = self._formatStateChanges(stateChanges)

        # Generate player choices
        choices = self._choiceGenerator.generateChoices(
            formatConfig=formatConfig,
            events=events,
            agentResponses=agentResponses,
            worldState=worldState,
        )

        output = PlayModeOutput(
            turnNumber=turnNumber,
            narrativeSummary=narrative,
            stateChanges=stateChangeList,
            playerChoices=choices,
            responseFormat=formatConfig.formatType,
            agentResponses=agentResponses,
            eventsTriggered=events,
        )

        logger.debug(
            f"Generated play mode output: turn={turnNumber}, "
            f"choices={len(choices)}, format={formatConfig.formatType.value}"
        )

        return output

    def _generateNarrative(
        self, agentResponses: list[AgentAction], events: list[Event]
    ) -> str:
        """Generate a narrative summary from agent responses and events.

        Args:
            agentResponses: Actions taken by agents.
            events: Events that occurred.

        Returns:
            Human-readable narrative summary.
        """
        parts: list[str] = []

        # Narrate events first
        for event in events:
            eventNarrative = event.data.get("narrative")
            if eventNarrative:
                parts.append(eventNarrative)
            elif event.name not in ("turn_start", "turn_end"):
                # Generate basic narrative for non-standard events
                parts.append(f"[{event.name}]")

        # Narrate agent responses
        for response in agentResponses:
            if response.content:
                # Include agent attribution in narrative
                parts.append(f"**{response.agentName}**: {response.content}")

        if not parts:
            return "Nothing significant happened this turn."

        return "\n\n".join(parts)

    def _formatStateChanges(
        self, stateChanges: dict[str, tuple[Any, Any]]
    ) -> list[StateChange]:
        """Convert state changes dict to structured StateChange list.

        Args:
            stateChanges: Dict of {key: (old_value, new_value)}.

        Returns:
            List of StateChange objects.
        """
        result: list[StateChange] = []

        for key, (oldValue, newValue) in stateChanges.items():
            delta = None
            if isinstance(oldValue, (int, float)) and isinstance(newValue, (int, float)):
                delta = newValue - oldValue

            result.append(
                StateChange(
                    key=key,
                    oldValue=oldValue,
                    newValue=newValue,
                    delta=delta,
                    source="turn",
                )
            )

        return result

    def applyPlayerChoice(
        self,
        playerInput: PlayerInput,
        choices: list[Choice],
        worldState: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply player's choice to world state.

        For MCQ/Yes-No: applies pre-computed impacts directly (no LLM cycle).
        For Free-text: returns empty dict (caller must handle LLM interpretation).

        Args:
            playerInput: Player's input.
            choices: Available choices.
            worldState: Current world state.

        Returns:
            Updated world state (or empty dict if LLM interpretation needed).
        """
        if playerInput.isFreeTextInput:
            # Free text requires LLM interpretation - return signal
            logger.debug("Free text input - requires LLM interpretation")
            return {}

        # Find the selected choice
        selectedChoice = None
        for choice in choices:
            if choice.id == playerInput.choiceId:
                selectedChoice = choice
                break

        if not selectedChoice:
            logger.warning(f"Choice not found: {playerInput.choiceId}")
            return worldState.copy()

        # Apply pre-computed impacts
        newState = worldState.copy()
        for key, delta in selectedChoice.predictedImpacts.items():
            if key in newState:
                if isinstance(newState[key], (int, float)) and isinstance(delta, (int, float)):
                    newState[key] = newState[key] + delta
                else:
                    newState[key] = delta
            else:
                newState[key] = delta

        logger.debug(
            f"Applied choice '{selectedChoice.id}' with {len(selectedChoice.predictedImpacts)} impacts"
        )

        return newState

    def requiresLlmInterpretation(self, playerInput: PlayerInput) -> bool:
        """Check if player input requires LLM interpretation.

        Args:
            playerInput: Player's input.

        Returns:
            True if LLM interpretation is needed (free text).
        """
        return playerInput.isFreeTextInput


class PlayModeStateTracker:
    """Tracks state changes during a turn for Play Mode output.

    Use this to capture state changes as they happen, then retrieve
    them in the format needed for PlayModeOutput.
    """

    def __init__(self) -> None:
        """Initialize the state tracker."""
        self._initialState: dict[str, Any] = {}
        self._changes: dict[str, tuple[Any, Any]] = {}

    def captureInitialState(self, worldState: dict[str, Any]) -> None:
        """Capture the world state at the start of a turn.

        Args:
            worldState: Current world state to capture.
        """
        self._initialState = worldState.copy()
        self._changes = {}

    def recordChange(self, key: str, newValue: Any) -> None:
        """Record a state change.

        Args:
            key: State key that changed.
            newValue: New value for the key.
        """
        oldValue = self._initialState.get(key)
        self._changes[key] = (oldValue, newValue)

    def detectChanges(self, newState: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
        """Detect all changes between initial state and new state.

        Args:
            newState: State to compare against initial.

        Returns:
            Dict of {key: (old_value, new_value)} for changed keys.
        """
        changes: dict[str, tuple[Any, Any]] = {}

        # Check for changed/new keys
        for key, newValue in newState.items():
            oldValue = self._initialState.get(key)
            if oldValue != newValue:
                changes[key] = (oldValue, newValue)

        # Check for removed keys
        for key in self._initialState:
            if key not in newState:
                changes[key] = (self._initialState[key], None)

        return changes

    def getChanges(self) -> dict[str, tuple[Any, Any]]:
        """Get all recorded changes.

        Returns:
            Dict of recorded state changes.
        """
        return self._changes.copy()

    def clear(self) -> None:
        """Clear all tracked state."""
        self._initialState = {}
        self._changes = {}
