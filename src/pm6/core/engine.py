"""Turn-based simulation engine.

Provides turn-based gameplay mechanics on top of the Simulation class.
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any, Callable

from pm6.core.cos_mode import ChiefOfStaffMode, CosModeConfig
from pm6.core.event_config import EventConfig
from pm6.core.play_mode import PlayModeGenerator, PlayModeStateTracker
from pm6.core.types import (
    ActionType,
    AgentAction,
    Choice,
    CosBriefingOutput,
    CosPlayState,
    EngineState,
    Event,
    MeetingState,
    OrchestratorDecision,
    PipelineConfig,
    PlayerInput,
    PlayModeOutput,
    PlayPhase,
    ResponseFormatConfig,
    ScheduledEvent,
    TurnMode,
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
        pipelineConfig: PipelineConfig | None = None,
    ):
        self._simulation = simulation
        self._autoAdvance = autoAdvance

        # Pipeline configuration (orchestrator vs initiative mode)
        self._pipelineConfig = pipelineConfig or PipelineConfig.default()

        # Engine state
        self._state = EngineState()
        self._scheduledEvents: list[ScheduledEvent] = []
        self._turnHooks: list[Callable[[TurnResult], None]] = []
        self._eventHandlers: dict[str, list[Callable[[Event], None]]] = {}

        # Run mode state
        self._stopRequested = False
        self._runSpeed = 1.0  # Seconds between auto turns

        # Orchestrator state
        self._lastOrchestratorDecision: OrchestratorDecision | None = None

        # Play Mode state
        self._playModeEnabled = False
        self._lastPlayModeOutput: PlayModeOutput | None = None
        self._pendingChoices: list[Choice] = []
        self._playModeGenerator: PlayModeGenerator | None = None
        self._stateTracker: PlayModeStateTracker | None = None
        self._pendingNextEventMapping: dict[str, str] = {}  # For choice→event chaining

        # Chief of Staff Mode state
        self._cosModeEnabled = False
        self._cosMode: ChiefOfStaffMode | None = None

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

    @property
    def pipelineConfig(self) -> PipelineConfig:
        """Get the pipeline configuration."""
        return self._pipelineConfig

    @pipelineConfig.setter
    def pipelineConfig(self, config: PipelineConfig) -> None:
        """Set the pipeline configuration."""
        self._pipelineConfig = config

    @property
    def lastOrchestratorDecision(self) -> OrchestratorDecision | None:
        """Get the last orchestrator decision (for debugging)."""
        return self._lastOrchestratorDecision

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

        # Get CPU agent actions based on turn mode
        if self._pipelineConfig.turnMode == TurnMode.ORCHESTRATOR:
            cpuActions = self._executeOrchestratedTurn(result.events)
        else:
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
    # Orchestrator Mode
    # =========================================================================

    def _executeOrchestratedTurn(self, events: list[Event]) -> list[AgentAction]:
        """Execute turn with orchestrator control.

        The orchestrator decides which agents should act based on:
        - Current events
        - World state
        - Available CPU agents
        - Game rules in its system prompt

        Args:
            events: Events that occurred this turn.

        Returns:
            List of actions taken by selected agents.
        """
        # Check if orchestrator exists
        orchestratorName = self._pipelineConfig.orchestratorName
        orchestrator = self._simulation.getAgent(orchestratorName)
        if not orchestrator:
            logger.warning(
                f"Orchestrator '{orchestratorName}' not found, falling back to initiative mode"
            )
            return self._executeCpuTurn()

        # Gather context
        worldState = self._simulation.getWorldState()
        cpuAgents = self._simulation.getCpuAgents()

        # Filter out the orchestrator from agents that can be woken
        availableAgents = [a for a in cpuAgents if a.name != orchestratorName]

        if not availableAgents:
            logger.info("No CPU agents available to wake")
            return []

        # Ask orchestrator who should act
        decision = self._askOrchestrator(events, worldState, availableAgents)
        self._lastOrchestratorDecision = decision

        logger.info(
            f"Orchestrator decided to wake: {decision.agentsToWake} "
            f"(reasoning: {decision.reasoning[:100]}...)"
        )

        # Execute only selected agents
        actions: list[AgentAction] = []
        for agentName in decision.agentsToWake:
            # Get specific instruction if provided
            instruction = decision.instructions.get(agentName)
            action = self._generateCpuActionWithInstruction(agentName, instruction)
            if action:
                actions.append(action)

        return actions

    def _askOrchestrator(
        self,
        events: list[Event],
        worldState: dict[str, Any],
        availableAgents: list,
    ) -> OrchestratorDecision:
        """Query orchestrator for turn decisions.

        Args:
            events: Events that occurred this turn.
            worldState: Current world state.
            availableAgents: List of available CPU agents.

        Returns:
            OrchestratorDecision with agents to wake and instructions.
        """
        orchestratorName = self._pipelineConfig.orchestratorName

        prompt = self._buildOrchestratorPrompt(events, worldState, availableAgents)

        try:
            response = self._simulation.interact(
                agentName=orchestratorName,
                userInput=prompt,
                situationType="orchestrator_decision",
            )

            return self._parseOrchestratorResponse(response.content, availableAgents)

        except Exception as e:
            logger.error(f"Orchestrator failed: {e}")
            # Return empty decision on failure
            return OrchestratorDecision(reasoning=f"Error: {e}")

    def _buildOrchestratorPrompt(
        self,
        events: list[Event],
        worldState: dict[str, Any],
        availableAgents: list,
    ) -> str:
        """Build the prompt for the orchestrator.

        Args:
            events: Events that occurred this turn.
            worldState: Current world state.
            availableAgents: List of available CPU agents.

        Returns:
            Formatted prompt string.
        """
        # Format events
        eventLines = []
        for event in events:
            eventLines.append(f"- {event.name}: {event.data}")
        eventsStr = "\n".join(eventLines) if eventLines else "(no events)"

        # Format agents
        agentLines = []
        for agent in availableAgents:
            agentLines.append(f"- {agent.name}: {agent.role}")
        agentsStr = "\n".join(agentLines)

        # Format world state
        stateStr = self._formatWorldState(worldState)

        return f"""TURN {self._state.currentTurn} - ORCHESTRATOR DECISION

EVENTS THIS TURN:
{eventsStr}

CURRENT WORLD STATE:
{stateStr}

AVAILABLE AGENTS:
{agentsStr}

Based on the events, world state, and your game rules, decide which agents (if any) should act this turn.

Respond in this exact JSON format:
{{
    "agentsToWake": ["agent1", "agent2"],
    "instructions": {{
        "agent1": "specific instruction for agent1",
        "agent2": "specific instruction for agent2"
    }},
    "reasoning": "brief explanation of why these agents should act",
    "skipPlayerTurn": false
}}

Rules:
- Only wake agents that have something relevant to do based on events/state
- You can wake 0 agents if nothing requires attention
- Instructions are optional but help agents respond appropriately
- Set skipPlayerTurn to true only if the player shouldn't act this turn
"""

    def _parseOrchestratorResponse(
        self, content: str, availableAgents: list
    ) -> OrchestratorDecision:
        """Parse the orchestrator's response into a decision.

        Args:
            content: Raw response content from orchestrator.
            availableAgents: List of available agents (for validation).

        Returns:
            Parsed OrchestratorDecision.
        """
        import json
        import re

        logger.debug(f"Parsing orchestrator response: {content[:500]}...")

        # Try to extract JSON from response
        jsonStr = None

        # First try: Look for ```json ... ``` code block
        codeBlockMatch = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        if codeBlockMatch:
            jsonStr = codeBlockMatch.group(1)
            logger.debug("Found JSON in code block")

        # Second try: Look for raw JSON object
        if not jsonStr:
            jsonMatch = re.search(r"\{[\s\S]*\}", content)
            if jsonMatch:
                jsonStr = jsonMatch.group()
                logger.debug("Found raw JSON object")

        if jsonStr:
            try:
                data = json.loads(jsonStr)

                # Validate agent names
                validAgentNames = {a.name for a in availableAgents}
                agentsToWake = [
                    name
                    for name in data.get("agentsToWake", [])
                    if name in validAgentNames
                ]

                # Filter instructions to only valid agents
                instructions = {
                    k: v
                    for k, v in data.get("instructions", {}).items()
                    if k in validAgentNames
                }

                return OrchestratorDecision(
                    agentsToWake=agentsToWake,
                    instructions=instructions,
                    reasoning=data.get("reasoning", ""),
                    skipPlayerTurn=data.get("skipPlayerTurn", False),
                )

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse orchestrator JSON: {e}")
                logger.warning(f"Attempted to parse: {jsonStr[:200]}...")

        # Fallback: try to extract agent names from text
        logger.warning("Using fallback parsing for orchestrator response")
        logger.warning(f"Raw response was: {content}")
        validAgentNames = {a.name for a in availableAgents}
        foundAgents = [name for name in validAgentNames if name.lower() in content.lower()]

        return OrchestratorDecision(
            agentsToWake=foundAgents,
            reasoning=f"Fallback parse: {content[:200]}",
        )

    def _generateCpuActionWithInstruction(
        self, agentName: str, instruction: str | None = None
    ) -> AgentAction | None:
        """Generate an action for a CPU agent with optional instruction.

        Args:
            agentName: Name of the CPU agent.
            instruction: Optional specific instruction from orchestrator.

        Returns:
            AgentAction or None if agent has nothing to say.
        """
        worldState = self._simulation.getWorldState()

        # Build prompt with or without instruction
        if instruction:
            prompt = f"""The game master has directed you to act this turn.

INSTRUCTION: {instruction}

Current world state:
{self._formatWorldState(worldState)}

Respond in-character based on the instruction. Keep your response focused and brief."""
        else:
            prompt = f"""It's your turn to act in the simulation.

Current world state:
{self._formatWorldState(worldState)}

If you have something to say to the player (the {self._simulation.getPlayerAgentName() or 'user'}), respond with your message.
If you have nothing to say, respond with exactly: [NOTHING]

Keep your response brief and in-character."""

        try:
            response = self._simulation.interact(
                agentName=agentName,
                userInput=prompt,
                situationType="orchestrated_action",
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
                metadata={"instruction": instruction} if instruction else {},
            )

        except Exception as e:
            logger.warning(f"Failed to generate orchestrated action for {agentName}: {e}")
            return None

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

    def scheduleEventFromConfig(
        self,
        config: EventConfig,
        turnOverride: int | None = None,
    ) -> None:
        """Schedule an event from an EventConfig.

        Creates an event with narrative and choices from the config,
        properly formatted for the choice generator to extract.

        Args:
            config: EventConfig to schedule.
            turnOverride: Override the turn number from config.
        """
        turn = turnOverride if turnOverride is not None else config.turn
        eventData = config.toEventData()

        event = Event(
            name=config.name,
            data=eventData,
            source="config",
        )
        scheduled = ScheduledEvent(
            turn=turn,
            event=event,
            recurring=False,
            interval=1,
        )
        self._scheduledEvents.append(scheduled)
        logger.info(
            f"Scheduled event '{config.name}' for turn {turn} "
            f"with {len(config.choices)} choices"
        )

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
            "playModeEnabled": self._playModeEnabled,
        }

    # =========================================================================
    # Play Mode
    # =========================================================================

    def enablePlayMode(
        self,
        initialEventConfig: EventConfig | None = None,
        autoBootstrap: bool = True,
    ) -> None:
        """Enable Play Mode for end-player experience.

        Play Mode provides:
        - Narrative summaries instead of raw responses
        - Pre-computed choices with impact previews
        - State change visualization

        Args:
            initialEventConfig: Optional initial event to schedule for Turn 1.
            autoBootstrap: If True and no initialEventConfig provided,
                          try to load 'initial' event from simulation.
        """
        self._playModeEnabled = True
        self._playModeGenerator = PlayModeGenerator()
        self._stateTracker = PlayModeStateTracker()
        self._pendingNextEventMapping = {}

        # Bootstrap: Schedule initial event
        if initialEventConfig:
            self.scheduleEventFromConfig(initialEventConfig, turnOverride=1)
            logger.info(f"Play Mode enabled with initial event: {initialEventConfig.name}")
        elif autoBootstrap:
            # Try to load initial event config from simulation
            initialConfig = self._simulation.getEventConfig("initial")
            if initialConfig:
                self.scheduleEventFromConfig(initialConfig, turnOverride=1)
                logger.info(f"Play Mode enabled with auto-loaded initial event: {initialConfig.name}")
            else:
                logger.info("Play Mode enabled (no initial event configured)")
        else:
            logger.info("Play Mode enabled (bootstrap disabled)")

    def disablePlayMode(self) -> None:
        """Disable Play Mode and return to standard mode."""
        self._playModeEnabled = False
        self._playModeGenerator = None
        self._stateTracker = None
        self._lastPlayModeOutput = None
        self._pendingChoices = []
        self._pendingNextEventMapping = {}
        logger.info("Play Mode disabled")

    @property
    def isPlayModeEnabled(self) -> bool:
        """Check if Play Mode is enabled."""
        return self._playModeEnabled

    @property
    def lastPlayModeOutput(self) -> PlayModeOutput | None:
        """Get the last Play Mode output."""
        return self._lastPlayModeOutput

    def stepPlayMode(
        self, formatConfig: ResponseFormatConfig | None = None
    ) -> PlayModeOutput:
        """Execute a turn and return Play Mode output.

        This is the main entry point for Play Mode. It:
        1. Captures initial state
        2. Executes the turn (events + agents)
        3. Detects state changes
        4. Generates narrative + choices
        5. Captures next event mapping for chaining
        6. Returns PlayModeOutput for the player view

        Args:
            formatConfig: Optional response format override.

        Returns:
            PlayModeOutput ready for rendering.

        Raises:
            RuntimeError: If Play Mode is not enabled.
        """
        if not self._playModeEnabled:
            raise RuntimeError("Play Mode is not enabled. Call enablePlayMode() first.")

        if self._playModeGenerator is None or self._stateTracker is None:
            self.enablePlayMode()

        # Get response format config
        if formatConfig is None:
            formatConfig = self._simulation.getDefaultResponseFormat()

        # Capture initial state
        initialState = self._simulation.getWorldState()
        self._stateTracker.captureInitialState(initialState)

        # Execute the turn
        turnResult = self.step()

        # Detect state changes
        finalState = self._simulation.getWorldState()
        stateChanges = self._stateTracker.detectChanges(finalState)

        # Capture next event mapping from events (for choice chaining)
        self._pendingNextEventMapping = {}
        for event in turnResult.events:
            nextMapping = event.data.get("nextEventMapping", {})
            if nextMapping:
                self._pendingNextEventMapping.update(nextMapping)
                logger.debug(f"Captured next event mapping from {event.name}: {nextMapping}")

        # Generate Play Mode output
        output = self._playModeGenerator.generateOutput(
            turnNumber=turnResult.turnNumber,
            agentResponses=turnResult.cpuActions,
            events=turnResult.events,
            stateChanges=stateChanges,
            formatConfig=formatConfig,
            worldState=finalState,
        )

        # Store for later reference
        self._lastPlayModeOutput = output
        self._pendingChoices = output.playerChoices

        logger.info(
            f"Play Mode turn {output.turnNumber}: "
            f"{len(output.playerChoices)} choices, "
            f"{len(output.stateChanges)} state changes"
        )

        return output

    def submitPlayerChoice(self, choiceId: str) -> dict[str, Any]:
        """Submit a player's choice selection (for MCQ/Yes-No).

        This applies the pre-computed impacts without an LLM call.
        Also schedules the next event based on the choice mapping.

        Args:
            choiceId: ID of the selected choice.

        Returns:
            Updated world state.

        Raises:
            ValueError: If choice ID is invalid.
            RuntimeError: If no pending choices.
        """
        if not self._pendingChoices:
            raise RuntimeError("No pending choices. Execute stepPlayMode() first.")

        if self._playModeGenerator is None:
            raise RuntimeError("Play Mode generator not initialized.")

        # Create player input
        playerInput = PlayerInput(
            choiceId=choiceId,
            turnNumber=self._state.currentTurn,
        )

        # Find and validate choice
        selectedChoice = None
        for choice in self._pendingChoices:
            if choice.id == choiceId:
                selectedChoice = choice
                break

        if selectedChoice is None:
            validIds = [c.id for c in self._pendingChoices]
            raise ValueError(
                f"Invalid choice ID: '{choiceId}'. Valid IDs: {validIds}"
            )

        # Apply the choice
        currentState = self._simulation.getWorldState()
        newState = self._playModeGenerator.applyPlayerChoice(
            playerInput=playerInput,
            choices=self._pendingChoices,
            worldState=currentState,
        )

        # Update simulation state
        if newState:
            self._simulation.setWorldState(newState)

        # Schedule next event based on choice (for event chaining)
        if self._pendingNextEventMapping and choiceId in self._pendingNextEventMapping:
            nextEventName = self._pendingNextEventMapping[choiceId]
            nextEventConfig = self._simulation.getEventConfig(nextEventName)
            if nextEventConfig:
                # Schedule for next turn
                nextTurn = self._state.currentTurn + 1
                self.scheduleEventFromConfig(nextEventConfig, turnOverride=nextTurn)
                logger.info(f"Scheduled next event '{nextEventName}' for turn {nextTurn}")
            else:
                logger.warning(f"Next event config not found: {nextEventName}")

        # Clear pending state
        self._pendingChoices = []
        self._pendingNextEventMapping = {}

        logger.info(f"Applied player choice: {choiceId}")

        return newState

    def submitFreeText(self, text: str) -> PlayModeOutput:
        """Submit free-form text input from player.

        This requires an LLM call to interpret the text.

        Args:
            text: Player's free-form text input.

        Returns:
            New PlayModeOutput after interpretation.

        Raises:
            RuntimeError: If Play Mode is not enabled.
        """
        if not self._playModeEnabled:
            raise RuntimeError("Play Mode is not enabled.")

        if self._playModeGenerator is None:
            raise RuntimeError("Play Mode generator not initialized.")

        logger.info(f"Processing free text input: {text[:50]}...")

        # Create player input for interpretation
        playerInput = PlayerInput(
            freeText=text,
            turnNumber=self._state.currentTurn,
        )

        # For free text, we need to interpret via LLM
        # Use the orchestrator or a dedicated interpreter agent
        interpretedResponse = self._interpretFreeText(text)

        # Clear pending choices
        self._pendingChoices = []

        # Execute next turn with the interpreted action
        return self.stepPlayMode()

    def _interpretFreeText(self, text: str) -> str:
        """Interpret free-form player text via LLM.

        Args:
            text: Player's text to interpret.

        Returns:
            Interpreted action/response.
        """
        # Use orchestrator or player agent to interpret
        playerAgentName = self._simulation.getPlayerAgentName()
        if playerAgentName:
            try:
                response = self._simulation.interact(
                    agentName=playerAgentName,
                    userInput=text,
                    situationType="player_action",
                )
                return response.content
            except Exception as e:
                logger.warning(f"Failed to interpret free text: {e}")
                return text

        return text

    def getPendingChoices(self) -> list[Choice]:
        """Get the list of pending choices awaiting player input.

        Returns:
            List of available choices.
        """
        return self._pendingChoices.copy()

    def hasPendingChoices(self) -> bool:
        """Check if there are pending choices.

        Returns:
            True if player needs to make a choice.
        """
        return len(self._pendingChoices) > 0

    # =========================================================================
    # Chief of Staff Mode
    # =========================================================================

    def enableCosMode(self, config: CosModeConfig | None = None) -> None:
        """Enable Chief of Staff mode for intermediary gameplay.

        CoS mode provides:
        - Briefing phase: CoS aggregates agent positions
        - Meeting phase: Free-text conversations with specific agents
        - Decision phase: Strategic choices

        Args:
            config: CoS mode configuration.
        """
        self._cosModeEnabled = True
        self._cosMode = ChiefOfStaffMode(self._simulation, config)
        logger.info("Chief of Staff mode enabled")

    def disableCosMode(self) -> None:
        """Disable Chief of Staff mode."""
        self._cosModeEnabled = False
        self._cosMode = None
        logger.info("Chief of Staff mode disabled")

    @property
    def isCosModeEnabled(self) -> bool:
        """Check if CoS mode is enabled."""
        return self._cosModeEnabled

    @property
    def cosPlayState(self) -> CosPlayState | None:
        """Get current CoS play state."""
        if self._cosMode:
            return self._cosMode.state
        return None

    @property
    def cosPhase(self) -> PlayPhase | None:
        """Get current CoS phase."""
        if self._cosMode:
            return self._cosMode.phase
        return None

    def stepCosMode(
        self,
        formatConfig: ResponseFormatConfig | None = None,
    ) -> CosBriefingOutput:
        """Execute a turn in CoS mode and return briefing.

        This is the main entry point for CoS mode. It:
        1. Executes the turn (events + agents respond behind scenes)
        2. Generates CoS briefing with agent summaries
        3. Prepares strategic choices
        4. Returns briefing for player view

        Args:
            formatConfig: Optional response format override.

        Returns:
            CosBriefingOutput for rendering.

        Raises:
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled. Call enableCosMode() first.")

        # Reset CoS state for new turn
        self._cosMode.reset()

        # Get response format config
        if formatConfig is None:
            formatConfig = self._simulation.getDefaultResponseFormat()

        # Capture initial state
        initialState = self._simulation.getWorldState()
        if self._stateTracker:
            self._stateTracker.captureInitialState(initialState)

        # Execute the turn
        turnResult = self.step()

        # Extract event summary from events
        eventSummary = ""
        for event in turnResult.events:
            narrative = event.data.get("narrative", "")
            if narrative:
                eventSummary = narrative
                break

        # Extract strategic choices from events
        strategicChoices = []
        for event in turnResult.events:
            choices_data = event.data.get("choices", [])
            for c in choices_data:
                choice = Choice(
                    id=c.get("id", ""),
                    text=c.get("text", ""),
                    predictedImpacts=c.get("impacts", {}),
                    source="event",
                )
                strategicChoices.append(choice)
            # Capture next event mapping
            nextMapping = event.data.get("nextEventMapping", {})
            if nextMapping:
                self._pendingNextEventMapping.update(nextMapping)

        # Generate agent response summaries (token optimization)
        # In a full implementation, we'd batch-call all agents here
        # For now, use placeholder summaries based on agent configs
        agentResponses = {}
        for action in turnResult.cpuActions:
            agentResponses[action.agentName] = action.content[:200] + "..." if len(action.content) > 200 else action.content

        # Generate CoS briefing
        briefing = self._cosMode.generateBriefing(
            turnNumber=turnResult.turnNumber,
            eventSummary=eventSummary,
            strategicChoices=strategicChoices,
            agentResponses=agentResponses,
        )

        # Store choices for later
        self._pendingChoices = strategicChoices

        logger.info(
            f"CoS Mode turn {briefing.turnNumber}: "
            f"{len(briefing.agentBriefs)} agent briefs, "
            f"{len(briefing.strategicChoices)} choices"
        )

        return briefing

    def cosStartMeeting(self, agentName: str) -> MeetingState | None:
        """Start a meeting with an agent in CoS mode.

        Args:
            agentName: Name of agent to meet.

        Returns:
            MeetingState or None if agent not meetable.

        Raises:
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled.")

        meeting = self._cosMode.startMeeting(agentName)
        if meeting:
            logger.info(f"Started CoS meeting with {agentName}")
        return meeting

    def cosSendMessage(self, message: str) -> str | None:
        """Send a message in the current CoS meeting.

        Args:
            message: Player's message to the agent.

        Returns:
            Agent's response or None if not in meeting.

        Raises:
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled.")

        if not self._cosMode.isInMeeting:
            logger.warning("Not in a meeting")
            return None

        # Get agent for LLM call
        meeting = self._cosMode.currentMeeting
        if not meeting:
            return None

        agentName = meeting.agentName

        # Build context from meeting history
        conversationContext = "\n".join(
            f"{'PM' if m.role == 'player' else agentName}: {m.content}"
            for m in meeting.history
        )

        # Call the agent's LLM
        try:
            response = self._simulation.interact(
                agentName=agentName,
                userInput=f"{conversationContext}\n\nPM: {message}",
                situationType="meeting_conversation",
            )

            # Store the actual response in meeting history
            meeting.addMessage("player", message)
            meeting.addMessage("agent", response.content)

            return response.content
        except Exception as e:
            logger.error(f"Error in meeting conversation: {e}")
            return f"[Communication error: {str(e)}]"

    def cosEndMeeting(self) -> CosBriefingOutput | None:
        """End the current meeting and return to briefing.

        Returns:
            Updated briefing output.

        Raises:
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled.")

        briefing = self._cosMode.endMeeting()

        # Update game time in world state
        self._cosMode.updateGameTime()

        return briefing

    def cosProceedToDecision(self) -> CosBriefingOutput | None:
        """Proceed from briefing/meeting to decision phase.

        Returns:
            Briefing output in decision phase.

        Raises:
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled.")

        # Update game time before decision
        self._cosMode.updateGameTime()

        return self._cosMode.proceedToDecision()

    def cosSubmitDecision(self, choiceId: str) -> dict[str, Any]:
        """Submit a strategic decision in CoS mode.

        Similar to submitPlayerChoice but for CoS flow.

        Args:
            choiceId: ID of the selected strategic choice.

        Returns:
            Updated world state.

        Raises:
            ValueError: If choice ID is invalid.
            RuntimeError: If CoS mode is not enabled.
        """
        if not self._cosModeEnabled or not self._cosMode:
            raise RuntimeError("CoS mode is not enabled.")

        # Delegate to standard choice submission
        return self.submitPlayerChoice(choiceId)

    def cosGetMeetableAgents(self) -> list[dict[str, Any]]:
        """Get list of agents available for meeting.

        Returns:
            List of dicts with agent name and role.
        """
        if not self._cosModeEnabled or not self._cosMode:
            return []

        agents = self._cosMode.getMeetableAgents()
        return [{"name": a.name, "role": a.role} for a in agents]

    def cosGetCurrentMeeting(self) -> MeetingState | None:
        """Get current meeting state if in a meeting.

        Returns:
            MeetingState or None.
        """
        if not self._cosModeEnabled or not self._cosMode:
            return None
        return self._cosMode.currentMeeting
