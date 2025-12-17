"""Chief of Staff Mode for Play Mode.

Implements the CoS intermediary pattern:
- Briefing phase: CoS aggregates agent positions
- Meeting phase: Free-text conversations with specific agents
- Decision phase: Strategic choices

Token optimization:
- Batch agent responses in a single LLM call
- Only call individual agent LLM during meetings
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pm6.core.types import (
    AgentBrief,
    Choice,
    CosBriefingOutput,
    CosPlayState,
    MeetingState,
    PlayPhase,
)

if TYPE_CHECKING:
    from pm6.agents import AgentConfig
    from pm6.core.simulation import Simulation

logger = logging.getLogger("pm6.core.cos_mode")

# Hours spent per meeting
MEETING_HOURS_COST = 7


@dataclass
class CosModeConfig:
    """Configuration for Chief of Staff mode.

    Attributes:
        chiefOfStaffName: Name of the CoS agent.
        meetingHoursCost: Hours spent per meeting.
        enableTokenOptimization: Use batch calls for agent responses.
    """

    chiefOfStaffName: str = "chief_of_staff"
    meetingHoursCost: int = 7
    enableTokenOptimization: bool = True


class ChiefOfStaffMode:
    """Manages Chief of Staff play mode.

    Handles the briefing → meeting → decision flow.
    """

    def __init__(
        self,
        simulation: Simulation,
        config: CosModeConfig | None = None,
    ) -> None:
        """Initialize CoS mode.

        Args:
            simulation: The simulation instance.
            config: CoS mode configuration.
        """
        self._simulation = simulation
        self._config = config or CosModeConfig()
        self._state = CosPlayState()
        self._cachedAgentBriefs: dict[str, AgentBrief] = {}

    @property
    def state(self) -> CosPlayState:
        """Get current CoS play state."""
        return self._state

    @property
    def phase(self) -> PlayPhase:
        """Get current phase."""
        return self._state.phase

    @property
    def isInMeeting(self) -> bool:
        """Check if currently in a meeting."""
        return self._state.isInMeeting()

    @property
    def currentMeeting(self) -> MeetingState | None:
        """Get current meeting state."""
        return self._state.currentMeeting

    def reset(self) -> None:
        """Reset CoS state for new turn."""
        self._state = CosPlayState()
        self._cachedAgentBriefs = {}

    def getMeetableAgents(self) -> list[AgentConfig]:
        """Get list of agents available for meeting.

        Returns:
            List of meetable AgentConfig objects.
        """
        meetable = []
        for name in self._simulation.listAgents():
            config = self._simulation.getAgent(name)
            if config and config.meetable:
                meetable.append(config)
        return meetable

    def generateBriefing(
        self,
        turnNumber: int,
        eventSummary: str,
        strategicChoices: list[Choice],
        agentResponses: dict[str, str] | None = None,
    ) -> CosBriefingOutput:
        """Generate a briefing from Chief of Staff.

        If agentResponses is provided, uses those summaries.
        Otherwise generates them (requires LLM calls).

        Args:
            turnNumber: Current turn number.
            eventSummary: Summary of events that triggered this briefing.
            strategicChoices: Available strategic decisions.
            agentResponses: Pre-computed agent response summaries.

        Returns:
            CosBriefingOutput for rendering.
        """
        # Get current game time
        worldState = self._simulation.getWorldState()
        gameTime = worldState.get("turn_date", datetime.now().isoformat())

        # Add hours elapsed
        if self._state.totalHoursSpent > 0:
            try:
                dt = datetime.fromisoformat(gameTime.replace("Z", "+00:00"))
                dt += timedelta(hours=self._state.totalHoursSpent)
                gameTime = dt.isoformat()
            except (ValueError, TypeError):
                pass

        # Generate agent briefs
        agentBriefs = []
        meetableAgents = []

        for agentConfig in self.getMeetableAgents():
            agentName = agentConfig.name

            # Get summary from provided responses or cache
            summary = ""
            if agentResponses and agentName in agentResponses:
                summary = agentResponses[agentName]
            elif agentName in self._cachedAgentBriefs:
                agentBriefs.append(self._cachedAgentBriefs[agentName])
                meetableAgents.append(agentName)
                continue

            # Create brief
            brief = AgentBrief(
                agentName=agentName,
                agentRole=agentConfig.role,
                summary=summary or f"Awaiting input from {agentConfig.role}",
                recommendation="",
                urgency="medium",
                meetable=True,
            )
            agentBriefs.append(brief)
            meetableAgents.append(agentName)
            self._cachedAgentBriefs[agentName] = brief

        # Generate CoS narrative
        cosNarrative = self._generateCosNarrative(
            eventSummary, agentBriefs, self._state.agentsMet
        )

        # Create briefing output
        briefing = CosBriefingOutput(
            turnNumber=turnNumber,
            gameTime=gameTime,
            hoursElapsed=self._state.totalHoursSpent,
            eventSummary=eventSummary,
            agentBriefs=agentBriefs,
            meetableAgents=meetableAgents,
            chiefOfStaffNarrative=cosNarrative,
            strategicChoices=strategicChoices,
        )

        self._state.currentBriefing = briefing
        self._state.turnStartTime = gameTime
        self._state.phase = PlayPhase.BRIEFING

        return briefing

    def _generateCosNarrative(
        self,
        eventSummary: str,
        briefs: list[AgentBrief],
        agentsMet: list[str],
    ) -> str:
        """Generate Chief of Staff's narrative framing.

        Args:
            eventSummary: Summary of events.
            briefs: Agent briefings.
            agentsMet: Agents already met this turn.

        Returns:
            CoS narrative text.
        """
        lines = ["**Chief of Staff briefing:**"]

        if eventSummary:
            lines.append(f"\n{eventSummary}")

        lines.append("\n**Your advisors' positions:**")

        for brief in briefs:
            met_marker = " *(met)*" if brief.agentName in agentsMet else ""
            lines.append(f"• **{brief.agentRole}**{met_marker}: {brief.summary}")

        if agentsMet:
            lines.append(f"\n*Time spent in consultations: {self._state.totalHoursSpent} hours*")

        lines.append("\nWho would you like to speak with directly, Prime Minister?")
        lines.append("Or proceed to your decision when ready.")

        return "\n".join(lines)

    def startMeeting(self, agentName: str) -> MeetingState | None:
        """Start a meeting with an agent.

        Args:
            agentName: Name of agent to meet.

        Returns:
            MeetingState or None if agent not meetable.
        """
        # Validate agent is meetable
        agentConfig = self._simulation.getAgent(agentName)
        if not agentConfig or not agentConfig.meetable:
            logger.warning(f"Agent {agentName} is not meetable")
            return None

        # Start meeting
        self._state.startMeeting(agentName, agentConfig.role)

        # Get the agent's initial statement based on their brief
        brief = self._cachedAgentBriefs.get(agentName)
        initialStatement = ""
        if brief:
            initialStatement = (
                f"Prime Minister, thank you for meeting with me. "
                f"{brief.summary} "
                f"What would you like to discuss?"
            )
        else:
            initialStatement = (
                f"Prime Minister, thank you for meeting with me. "
                f"What would you like to discuss?"
            )

        # Add agent's opening to conversation
        self._state.currentMeeting.addMessage("agent", initialStatement)

        logger.info(f"Started meeting with {agentName}")
        return self._state.currentMeeting

    def sendMeetingMessage(self, playerMessage: str) -> str | None:
        """Send a message in the current meeting.

        This triggers an LLM call to the agent for response.

        Args:
            playerMessage: Player's message to the agent.

        Returns:
            Agent's response or None if not in meeting.
        """
        if not self._state.isInMeeting() or not self._state.currentMeeting:
            logger.warning("Not in a meeting")
            return None

        # Add player message to history
        self._state.currentMeeting.addMessage("player", playerMessage)

        # Get agent response (this is where we'd call the LLM)
        # For now, return a placeholder - actual implementation would call agent
        agentName = self._state.currentMeeting.agentName
        agentConfig = self._simulation.getAgent(agentName)

        # Build conversation context for LLM call
        # The actual LLM call would happen here
        # For now, we'll return a structured response that can be filled by the route handler
        response = f"[Agent {agentName} response to: {playerMessage[:50]}...]"

        # Add response to history
        self._state.currentMeeting.addMessage("agent", response)

        return response

    def endMeeting(self) -> CosBriefingOutput | None:
        """End the current meeting and return to briefing.

        Returns:
            Updated briefing output.
        """
        if not self._state.isInMeeting():
            logger.warning("Not in a meeting")
            return None

        agentName = self._state.currentMeeting.agentName if self._state.currentMeeting else "unknown"

        # End meeting (adds hours, records agent met)
        self._state.endMeeting(hoursSpent=self._config.meetingHoursCost)

        logger.info(f"Ended meeting with {agentName}, total hours: {self._state.totalHoursSpent}")

        # Update briefing with new time
        if self._state.currentBriefing:
            self._state.currentBriefing.hoursElapsed = self._state.totalHoursSpent
            # Regenerate narrative with updated met agents
            self._state.currentBriefing.chiefOfStaffNarrative = self._generateCosNarrative(
                self._state.currentBriefing.eventSummary,
                self._state.currentBriefing.agentBriefs,
                self._state.agentsMet,
            )
            return self._state.currentBriefing

        return None

    def proceedToDecision(self) -> CosBriefingOutput | None:
        """Proceed from briefing to decision phase.

        Returns:
            Briefing output in decision phase.
        """
        if self._state.phase == PlayPhase.MEETING:
            # End any active meeting first
            self.endMeeting()

        self._state.proceedToDecision()

        if self._state.currentBriefing:
            return self._state.currentBriefing

        return None

    def updateGameTime(self) -> str:
        """Update world state with elapsed time.

        Returns:
            New game time string.
        """
        if self._state.totalHoursSpent > 0:
            worldState = self._simulation.getWorldState()
            gameTime = worldState.get("turn_date", "")

            try:
                dt = datetime.fromisoformat(gameTime.replace("Z", "+00:00"))
                dt += timedelta(hours=self._state.totalHoursSpent)
                newTime = dt.isoformat()

                # Update world state
                worldState["turn_date"] = newTime
                self._simulation.setWorldState(worldState)

                logger.info(f"Updated game time: +{self._state.totalHoursSpent}h")
                return newTime
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to update game time: {e}")

        return self._simulation.getWorldState().get("turn_date", "")

    def toDict(self) -> dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "state": self._state.toDict(),
            "config": {
                "chiefOfStaffName": self._config.chiefOfStaffName,
                "meetingHoursCost": self._config.meetingHoursCost,
                "enableTokenOptimization": self._config.enableTokenOptimization,
            },
        }
