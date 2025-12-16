"""Turn-based simulation engine.

Provides turn-based gameplay mechanics on top of the Simulation class.
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any, Callable

from pm6.core.types import (
    ActionType,
    AgentAction,
    EngineState,
    Event,
    ScheduledEvent,
    TurnResult,
)

if TYPE_CHECKING:
    from pm6.core.simulation import Simulation

logger = logging.getLogger("pm6.core.engine")


class SimulationEngine:
    """Turn-based simulation engine.

    Wraps a Simulation instance to provide turn-based gameplay mechanics
    including CPU agent initiative, scheduled events, and run modes.

    Args:
        simulation: The Simulation instance to wrap.
        autoAdvance: Whether to automatically advance turns after player actions.

    Example:
        >>> sim = Simulation("my_sim")
        >>> sim.registerAgent(AgentConfig(name="pm", role="PM", controlledBy="player"))
        >>> sim.registerAgent(AgentConfig(name="advisor", role="Advisor", initiative=0.7))
        >>> engine = SimulationEngine(sim)
        >>> result = engine.step()  # Execute one turn
        >>> for action in result.cpuActions:
        ...     print(f"{action.agentName}: {action.content}")
    """

    def __init__(
        self,
        simulation: Simulation,
        autoAdvance: bool = False,
    ):
        self._simulation = simulation
        self._autoAdvance = autoAdvance

        # Engine state
        self._state = EngineState()
        self._scheduledEvents: list[ScheduledEvent] = []
        self._turnHooks: list[Callable[[TurnResult], None]] = []
        self._eventHandlers: dict[str, list[Callable[[Event], None]]] = {}

        # Run mode state
        self._stopRequested = False
        self._runSpeed = 1.0  # Seconds between auto turns

    @property
    def simulation(self) -> Simulation:
        """Get the underlying simulation."""
        return self._simulation

    @property
    def currentTurn(self) -> int:
        """Get the current turn number."""
        return self._state.currentTurn

    @property
    def isRunning(self) -> bool:
        """Check if engine is actively running (auto mode)."""
        return self._state.isRunning

    @property
    def isPaused(self) -> bool:
        """Check if engine is paused."""
        return self._state.isPaused

    @property
    def state(self) -> EngineState:
        """Get the engine state."""
        return self._state

    # =========================================================================
    # Turn Execution
    # =========================================================================

    def step(self) -> TurnResult:
        """Execute a single turn of the simulation.

        During a turn:
        1. Emit 'turn_start' event
        2. Process scheduled events
        3. Roll initiative for CPU agents
        4. Execute CPU agent actions
        5. Emit 'turn_end' event
        6. Increment turn counter

        Returns:
            TurnResult with actions taken and events fired.
        """
        self._state.currentTurn += 1
        turnNum = self._state.currentTurn

        result = TurnResult(turnNumber=turnNum)

        # Emit turn start event
        startEvent = Event(name="turn_start", data={"turn": turnNum})
        self._emitEvent(startEvent)
        result.events.append(startEvent)

        # Process scheduled events
        scheduled = self._processScheduledEvents(turnNum)
        result.events.extend(scheduled)

        # Get CPU agent actions
        cpuActions = self._executeCpuTurn()
        result.cpuActions = cpuActions

        # Track state changes
        # (In a more advanced implementation, we'd diff the state)

        # Emit turn end event
        endEvent = Event(name="turn_end", data={"turn": turnNum, "actions": len(cpuActions)})
        self._emitEvent(endEvent)
        result.events.append(endEvent)

        # Run turn hooks
        for hook in self._turnHooks:
            try:
                hook(result)
            except Exception as e:
                logger.warning(f"Turn hook error: {e}")

        # Store last result
        self._state.lastTurnResult = result

        logger.info(f"Completed turn {turnNum} with {len(cpuActions)} CPU actions")
        return result

    def _executeCpuTurn(self) -> list[AgentAction]:
        """Execute actions for CPU agents based on initiative.

        Returns:
            List of actions taken by CPU agents.
        """
        actions: list[AgentAction] = []

        for agent in self._simulation.getCpuAgents():
            # Roll against initiative
            if random.random() < agent.initiative:
                action = self._generateCpuAction(agent.name)
                if action:
                    actions.append(action)

        return actions

    def _generateCpuAction(self, agentName: str) -> AgentAction | None:
        """Generate an action for a CPU agent.

        Uses the LLM to decide what the agent wants to say/do based on
        the current world state.

        Args:
            agentName: Name of the CPU agent.

        Returns:
            AgentAction or None if agent has nothing to say.
        """
        agent = self._simulation.getAgent(agentName)
        worldState = self._simulation.getWorldState()

        # Build a prompt asking if the agent wants to speak
        initiativePrompt = f"""Based on the current situation, do you have something important to say or do?

Current world state:
{self._formatWorldState(worldState)}

If you have something to say to the player (the {self._simulation.getPlayerAgentName() or 'user'}), respond with your message.
If you have nothing urgent to say, respond with exactly: [NOTHING]

Keep your response brief and in-character."""

        try:
            response = self._simulation.interact(
                agentName=agentName,
                userInput=initiativePrompt,
                situationType="initiative_check",
            )

            content = response.content.strip()

            # Check if agent decided not to speak
            if content == "[NOTHING]" or not content:
                return None

            return AgentAction(
                agentName=agentName,
                actionType=ActionType.SPEAK,
                content=content,
                target=self._simulation.getPlayerAgentName(),
            )

        except Exception as e:
            logger.warning(f"Failed to generate CPU action for {agentName}: {e}")
            return None

    def _formatWorldState(self, state: dict[str, Any]) -> str:
        """Format world state for prompts."""
        lines = []
        for key, value in state.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines) if lines else "(empty)"

    # =========================================================================
    # Run Modes
    # =========================================================================

    def run(self, turns: int | None = None, speed: float = 1.0) -> list[TurnResult]:
        """Run the simulation for multiple turns automatically.

        Args:
            turns: Number of turns to run (None = run until stopped).
            speed: Seconds between turns.

        Returns:
            List of TurnResults from each turn.
        """
        self._state.isRunning = True
        self._state.isPaused = False
        self._stopRequested = False
        self._runSpeed = speed

        results: list[TurnResult] = []
        turnsExecuted = 0

        try:
            while not self._stopRequested:
                if self._state.isPaused:
                    time.sleep(0.1)
                    continue

                result = self.step()
                results.append(result)
                turnsExecuted += 1

                # Check turn limit
                if turns is not None and turnsExecuted >= turns:
                    break

                # Check if player input needed
                if result.playerPending:
                    break

                # Wait between turns
                if speed > 0:
                    time.sleep(speed)

        finally:
            self._state.isRunning = False

        return results

    def pause(self) -> None:
        """Pause auto-run mode."""
        self._state.isPaused = True
        logger.info("Engine paused")

    def resume(self) -> None:
        """Resume from paused state."""
        self._state.isPaused = False
        logger.info("Engine resumed")

    def stop(self) -> None:
        """Stop auto-run mode."""
        self._stopRequested = True
        self._state.isRunning = False
        logger.info("Engine stopped")

    # =========================================================================
    # Event Scheduling
    # =========================================================================

    def scheduleEvent(
        self,
        turn: int,
        eventName: str,
        data: dict[str, Any] | None = None,
        recurring: bool = False,
        interval: int = 1,
    ) -> None:
        """Schedule an event to fire on a specific turn.

        Args:
            turn: Turn number when event should fire.
            eventName: Name of the event.
            data: Event data payload.
            recurring: Whether event should repeat.
            interval: Turns between recurrences.
        """
        event = Event(name=eventName, data=data or {}, source="scheduled")
        scheduled = ScheduledEvent(
            turn=turn,
            event=event,
            recurring=recurring,
            interval=interval,
        )
        self._scheduledEvents.append(scheduled)
        logger.debug(f"Scheduled event '{eventName}' for turn {turn}")

    def cancelScheduledEvent(self, eventName: str) -> int:
        """Cancel all scheduled events with a given name.

        Args:
            eventName: Name of events to cancel.

        Returns:
            Number of events cancelled.
        """
        before = len(self._scheduledEvents)
        self._scheduledEvents = [
            se for se in self._scheduledEvents if se.event.name != eventName
        ]
        cancelled = before - len(self._scheduledEvents)
        if cancelled:
            logger.debug(f"Cancelled {cancelled} scheduled event(s) '{eventName}'")
        return cancelled

    def _processScheduledEvents(self, turn: int) -> list[Event]:
        """Process scheduled events for this turn.

        Args:
            turn: Current turn number.

        Returns:
            List of events that fired.
        """
        fired: list[Event] = []
        remaining: list[ScheduledEvent] = []

        for se in self._scheduledEvents:
            if se.turn == turn:
                self._emitEvent(se.event)
                fired.append(se.event)

                # Reschedule if recurring
                if se.recurring:
                    se.turn = turn + se.interval
                    remaining.append(se)
            else:
                remaining.append(se)

        self._scheduledEvents = remaining
        return fired

    # =========================================================================
    # Event Handling
    # =========================================================================

    def onEvent(self, eventName: str, handler: Callable[[Event], None]) -> None:
        """Register a handler for an event type.

        Args:
            eventName: Event name to handle.
            handler: Callback function.
        """
        if eventName not in self._eventHandlers:
            self._eventHandlers[eventName] = []
        self._eventHandlers[eventName].append(handler)

    def onTurn(self, handler: Callable[[TurnResult], None]) -> None:
        """Register a callback to run after each turn.

        Args:
            handler: Callback receiving TurnResult.
        """
        self._turnHooks.append(handler)

    def _emitEvent(self, event: Event) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: Event to emit.
        """
        handlers = self._eventHandlers.get(event.name, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler error for '{event.name}': {e}")

    # =========================================================================
    # State Management
    # =========================================================================

    def reset(self) -> None:
        """Reset engine state to initial values."""
        self._state = EngineState()
        self._scheduledEvents.clear()
        self._stopRequested = False
        logger.info("Engine reset")

    def setTurn(self, turn: int) -> None:
        """Set the current turn number.

        Args:
            turn: Turn number to set.
        """
        self._state.currentTurn = turn

    def getStats(self) -> dict[str, Any]:
        """Get engine statistics.

        Returns:
            Dictionary with engine stats.
        """
        return {
            "currentTurn": self._state.currentTurn,
            "isRunning": self._state.isRunning,
            "isPaused": self._state.isPaused,
            "scheduledEvents": len(self._scheduledEvents),
            "turnHooks": len(self._turnHooks),
            "eventHandlers": sum(len(h) for h in self._eventHandlers.values()),
        }
