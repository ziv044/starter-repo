"""Choice generator for Play Mode.

Aggregates choices from pre-scripted events and agent-generated suggestions,
resolves conflicts, and assigns IDs.
"""

import logging
from typing import Any

from pm6.core.types import (
    AgentAction,
    Choice,
    Event,
    ResponseFormatConfig,
    ResponseFormatType,
)

logger = logging.getLogger("pm6.core.choice_generator")


class ChoiceGenerator:
    """Generates and aggregates player choices from multiple sources.

    Sources:
    1. Pre-scripted choices from event configurations
    2. Agent-generated choices from their responses
    3. System-generated choices (yes/no, fallback)
    """

    def __init__(self) -> None:
        """Initialize the choice generator."""
        self._choiceLabels = ["A", "B", "C", "D", "E", "F", "G", "H"]

    def generateChoices(
        self,
        formatConfig: ResponseFormatConfig,
        events: list[Event] | None = None,
        agentResponses: list[AgentAction] | None = None,
        worldState: dict[str, Any] | None = None,
    ) -> list[Choice]:
        """Generate player choices based on format and available sources.

        Pre-scripted event choices take priority over agent-generated.

        Args:
            formatConfig: Response format configuration.
            events: Events that fired this turn (may contain pre-scripted choices).
            agentResponses: Agent responses (may contain suggested choices).
            worldState: Current world state for context.

        Returns:
            List of choices for the player.
        """
        choices: list[Choice] = []

        # Priority 1: Pre-scripted choices from events
        if events:
            eventChoices = self._extractEventChoices(events)
            if eventChoices:
                choices.extend(eventChoices)
                logger.debug(f"Using {len(eventChoices)} pre-scripted choices from events")

        # Priority 2: Agent-generated choices (only if no event choices)
        if not choices and agentResponses:
            agentChoices = self._extractAgentChoices(agentResponses)
            if agentChoices:
                choices.extend(agentChoices)
                logger.debug(f"Using {len(agentChoices)} agent-generated choices")

        # Priority 3: System-generated for Yes/No format
        if not choices and formatConfig.formatType == ResponseFormatType.YES_NO:
            choices = self._generateYesNoChoices()
            logger.debug("Generated yes/no choices")

        # Limit choices based on format config
        if formatConfig.formatType == ResponseFormatType.MCQ:
            choices = choices[: formatConfig.choiceCount]

        # Assign IDs if not already set
        choices = self._assignChoiceIds(choices, formatConfig)

        return choices

    def _extractEventChoices(self, events: list[Event]) -> list[Choice]:
        """Extract pre-scripted choices from events.

        Args:
            events: List of events to extract choices from.

        Returns:
            List of choices from events.
        """
        choices: list[Choice] = []

        for event in events:
            eventChoices = event.data.get("choices", [])
            for choiceData in eventChoices:
                if isinstance(choiceData, dict):
                    choice = Choice(
                        id=choiceData.get("id", ""),
                        text=choiceData.get("text", ""),
                        predictedImpacts=choiceData.get("impacts", {}),
                        source="event",
                    )
                    choices.append(choice)

        return choices

    def _extractAgentChoices(self, agentResponses: list[AgentAction]) -> list[Choice]:
        """Extract suggested choices from agent responses.

        Agents can include choices in their metadata under 'suggested_choices'.

        Args:
            agentResponses: List of agent actions.

        Returns:
            List of choices from agents.
        """
        choices: list[Choice] = []

        for response in agentResponses:
            suggestedChoices = response.metadata.get("suggested_choices", [])
            for choiceData in suggestedChoices:
                if isinstance(choiceData, dict):
                    choice = Choice(
                        id=choiceData.get("id", ""),
                        text=choiceData.get("text", ""),
                        predictedImpacts=choiceData.get("predicted_impacts", {}),
                        source="agent",
                        agentName=response.agentName,
                    )
                    choices.append(choice)

        return choices

    def _generateYesNoChoices(self) -> list[Choice]:
        """Generate standard yes/no choices.

        Returns:
            List with yes and no choices.
        """
        return [
            Choice(
                id="yes",
                text="Yes",
                predictedImpacts={},
                source="system",
            ),
            Choice(
                id="no",
                text="No",
                predictedImpacts={},
                source="system",
            ),
        ]

    def _assignChoiceIds(
        self, choices: list[Choice], formatConfig: ResponseFormatConfig
    ) -> list[Choice]:
        """Assign IDs to choices that don't have them.

        Args:
            choices: List of choices to process.
            formatConfig: Format configuration for ID style.

        Returns:
            Choices with IDs assigned.
        """
        result: list[Choice] = []

        for i, choice in enumerate(choices):
            if not choice.id:
                # Assign letter ID for MCQ, yes/no for binary
                if formatConfig.formatType == ResponseFormatType.YES_NO:
                    choice.id = "yes" if i == 0 else "no"
                else:
                    choice.id = self._choiceLabels[i] if i < len(self._choiceLabels) else str(i + 1)

            result.append(choice)

        return result

    def createChoiceFromImpacts(
        self,
        choiceId: str,
        text: str,
        impacts: dict[str, int | float],
        source: str = "system",
    ) -> Choice:
        """Create a choice with pre-computed impacts.

        Args:
            choiceId: Unique identifier for the choice.
            text: Display text.
            impacts: Pre-computed state changes.
            source: Source of the choice.

        Returns:
            A new Choice instance.
        """
        return Choice(
            id=choiceId,
            text=text,
            predictedImpacts=impacts,
            source=source,
        )

    def mergeChoices(
        self, primary: list[Choice], secondary: list[Choice], maxChoices: int = 4
    ) -> list[Choice]:
        """Merge two lists of choices, preferring primary.

        Args:
            primary: Primary choices (higher priority).
            secondary: Secondary choices (lower priority).
            maxChoices: Maximum number of choices to return.

        Returns:
            Merged list of choices.
        """
        result = list(primary)

        # Add secondary choices up to max
        for choice in secondary:
            if len(result) >= maxChoices:
                break
            # Avoid duplicates by text
            if not any(c.text == choice.text for c in result):
                result.append(choice)

        return result[:maxChoices]
