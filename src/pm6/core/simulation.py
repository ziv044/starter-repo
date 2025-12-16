"""Main Simulation class for pm6.

The Simulation class is the central orchestrator that:
- Manages agents and their configurations
- Maintains world state
- Routes interactions through cache and LLM
- Tracks costs and provides statistics
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from pm6.agents import (
    AgentConfig,
    AgentRelevanceDetector,
    AgentRouter,
    AgentStateUpdater,
    MemoryManager,
    MemoryPolicy,
    RelevanceScore,
)
from pm6.config import getSettings
from pm6.core.response import AgentResponse, InteractionResult
from pm6.core.rules import SimulationRules
from pm6.cost import (
    CostEstimate,
    CostEstimator,
    CostTracker,
    ModelRouter,
    ResponseCache,
    SignatureComponents,
    StateBucketer,
    TokenBudget,
    TokenBudgetManager,
    computeSignature,
)
from pm6.cost.responseCache import CachedResponse
from pm6.exceptions import (
    AgentNotFoundError,
    CostLimitError,
    RuleViolationError,
    SimulationError,
)
from pm6.llm import AnthropicClient
from pm6.metrics import PerformanceTracker
from pm6.state import (
    CheckpointManager,
    ReplayVerificationResult,
    SessionRecorder,
    SessionReplayer,
    Storage,
)
from pm6.tools import Tool, ToolCall, ToolRegistry, ToolResult

if TYPE_CHECKING:
    from pm6.reliability import StateSnapshot, TransactionManager
    from pm6.testing import (
        AgentComparator,
        AgentValidator,
        MockAnthropicClient,
        ScenarioTester,
        ValidationReport,
    )

logger = logging.getLogger("pm6.core")


class Simulation:
    """Main simulation orchestrator.

    Args:
        name: Unique name for this simulation.
        dbPath: Path for persistent storage.
        enableCache: Whether to use response caching.
        enableCostTracking: Whether to track costs.
        tokenBudget: Token budget configuration.
        maxCost: Maximum cost limit in USD (None for unlimited).
        rules: Simulation rules and constraints.
        testMode: Enable test mode with mock responses.
        mockClient: Custom mock client for test mode.
    """

    def __init__(
        self,
        name: str,
        dbPath: Path | None = None,
        enableCache: bool = True,
        enableCostTracking: bool = True,
        tokenBudget: TokenBudget | None = None,
        maxCost: float | None = None,
        rules: SimulationRules | None = None,
        testMode: bool = False,
        mockClient: MockAnthropicClient | None = None,
    ):
        settings = getSettings()
        self.name = name
        self._dbPath = dbPath or settings.dbPath
        self._maxCost = maxCost
        self._testMode = testMode

        # Initialize components
        self._storage = Storage(self._dbPath, name)
        self._checkpointManager = CheckpointManager(self._dbPath, name)
        self._costTracker = CostTracker() if enableCostTracking else None
        self._modelRouter = ModelRouter()
        cachePath = self._dbPath / name / "responses"
        self._responseCache = ResponseCache(cachePath) if enableCache else None
        self._stateBucketer = StateBucketer()
        self._agentRouter = AgentRouter()
        self._memoryManager = MemoryManager()
        self._tokenBudgetManager = TokenBudgetManager(budget=tokenBudget)
        self._relevanceDetector = AgentRelevanceDetector()
        self._stateUpdater = AgentStateUpdater()
        self._costEstimator = CostEstimator(defaultModel=settings.defaultModel)
        self._sessionRecorder = SessionRecorder(self._dbPath, name)
        self._performanceTracker = PerformanceTracker()
        self._toolRegistry = ToolRegistry()
        self._rules = rules or SimulationRules()
        self._turnCount = 0
        self._autoApplyStateUpdates = True  # Auto-apply updates after interactions

        # LLM client - use mock in test mode
        if testMode:
            if mockClient is not None:
                self._llmClient = mockClient
            else:
                from pm6.testing import MockAnthropicClient

                self._llmClient = MockAnthropicClient(
                    costTracker=self._costTracker,
                    modelRouter=self._modelRouter,
                )
            self._mockClient: MockAnthropicClient | None = self._llmClient  # type: ignore
        else:
            self._llmClient = AnthropicClient(
                costTracker=self._costTracker,
                modelRouter=self._modelRouter,
            )
            self._mockClient = None

        # Simulation state
        self._agents: dict[str, AgentConfig] = {}
        self._worldState: dict[str, Any] = {}
        self._history: list[InteractionResult] = []
        self._isRunning = False
        self._recordingEnabled = True  # Record by default
        self._playerAgentName: str | None = None

        logger.info(f"Initialized simulation: {name}")

    # Agent Management

    def registerAgent(self, config: AgentConfig) -> None:
        """Register an agent with the simulation.

        Args:
            config: Agent configuration.

        Raises:
            SimulationError: If agent already exists.
        """
        if config.name in self._agents:
            raise SimulationError(f"Agent '{config.name}' already registered")

        self._agents[config.name] = config
        self._agentRouter.addAgent(config)
        self._storage.saveAgent(config.name, config.model_dump())

        logger.info(f"Registered agent: {config.name}")

    def getAgent(self, name: str) -> AgentConfig:
        """Get an agent configuration.

        Args:
            name: Agent name.

        Returns:
            Agent configuration.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        if name not in self._agents:
            raise AgentNotFoundError(name)
        return self._agents[name]

    def listAgents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    # Player/CPU Agent Management

    def setPlayerAgent(self, name: str) -> None:
        """Set which agent is controlled by the player.

        Args:
            name: Name of the agent to set as player-controlled.

        Raises:
            AgentNotFoundError: If agent not found.
        """
        if name not in self._agents:
            raise AgentNotFoundError(name)
        self._playerAgentName = name
        # Also update the agent's controlledBy field
        self._agents[name].controlledBy = "player"

    def getPlayerAgent(self) -> AgentConfig | None:
        """Get the player-controlled agent configuration.

        Returns:
            AgentConfig for player agent, or None if not set.
        """
        if self._playerAgentName and self._playerAgentName in self._agents:
            return self._agents[self._playerAgentName]
        # Fallback: look for agent with controlledBy='player'
        for agent in self._agents.values():
            if agent.isPlayer:
                return agent
        return None

    def getPlayerAgentName(self) -> str | None:
        """Get the name of the player-controlled agent.

        Returns:
            Agent name or None if not set.
        """
        if self._playerAgentName:
            return self._playerAgentName
        player = self.getPlayerAgent()
        return player.name if player else None

    def getCpuAgents(self) -> list[AgentConfig]:
        """Get all CPU-controlled agents.

        Returns:
            List of AgentConfig for CPU agents.
        """
        return [agent for agent in self._agents.values() if agent.isCpu]

    def isPlayerAgent(self, name: str) -> bool:
        """Check if an agent is the player-controlled agent.

        Args:
            name: Agent name to check.

        Returns:
            True if this is the player agent.
        """
        if self._playerAgentName:
            return name == self._playerAgentName
        agent = self._agents.get(name)
        return agent.isPlayer if agent else False

    # Agent Relevance Detection

    def addAgentKeywords(
        self,
        agentName: str,
        keywords: list[str],
        weight: float = 1.0,
    ) -> None:
        """Add keyword-based relevance detection for an agent.

        Args:
            agentName: Agent name.
            keywords: Keywords that make this agent relevant.
            weight: Importance weight (0.0 to 1.0).
        """
        self._relevanceDetector.addKeywords(agentName, keywords, weight)

    def addAgentRelevanceCondition(
        self,
        agentName: str,
        condition: Callable[[dict[str, Any]], bool],
        weight: float = 1.0,
        description: str = "",
    ) -> None:
        """Add state-based relevance condition for an agent.

        Args:
            agentName: Agent name.
            condition: Function(worldState) -> bool.
            weight: Importance weight.
            description: Human-readable description.
        """
        self._relevanceDetector.addStateCondition(
            agentName, condition, weight, description
        )

    def setAgentAlwaysRelevant(self, agentName: str) -> None:
        """Mark an agent as always relevant for all interactions.

        Args:
            agentName: Agent name.
        """
        self._relevanceDetector.setAlwaysRelevant(agentName)

    def getRelevantAgents(
        self,
        userInput: str,
        situationType: str | None = None,
        topK: int | None = None,
    ) -> list[tuple[str, float]]:
        """Get agents relevant for a given input.

        Args:
            userInput: User's input text.
            situationType: Current situation type.
            topK: Return only top K agents.

        Returns:
            List of (agentName, relevanceScore) tuples.
        """
        agents = list(self._agents.values())
        relevant = self._relevanceDetector.getRelevantAgents(
            agents, userInput, self._worldState, situationType, topK
        )
        return [(agent.name, score.score) for agent, score in relevant]

    def scoreAgentRelevance(
        self,
        agentName: str,
        userInput: str,
        situationType: str | None = None,
    ) -> RelevanceScore:
        """Score how relevant an agent is for a given input.

        Args:
            agentName: Agent to score.
            userInput: User's input text.
            situationType: Current situation type.

        Returns:
            RelevanceScore with score and matched rules.
        """
        agent = self._agents.get(agentName)
        return self._relevanceDetector.scoreAgent(
            agentName, userInput, self._worldState, situationType, agent
        )

    @property
    def relevanceDetector(self) -> AgentRelevanceDetector:
        """Get the relevance detector for advanced configuration."""
        return self._relevanceDetector

    # Agent State Updates

    def addStateUpdateRule(
        self,
        agentName: str,
        key: str,
        value: Any,
        trigger: str = "always",
        triggerValue: Any = None,
        operation: str = "set",
    ) -> None:
        """Add a state update rule for an agent.

        Args:
            agentName: Agent name.
            key: State key to update.
            value: Value to set/apply.
            trigger: When to trigger (always, pattern, keyword).
            triggerValue: Value for pattern/keyword trigger.
            operation: How to apply (set, increment, append, merge).
        """
        if trigger == "always":
            self._stateUpdater.addAlwaysUpdate(agentName, key, value, operation)
        elif trigger == "pattern" and triggerValue:
            self._stateUpdater.addPatternUpdate(
                agentName, triggerValue, key, value, operation
            )
        elif trigger == "keyword" and triggerValue:
            keywords = triggerValue if isinstance(triggerValue, list) else [triggerValue]
            self._stateUpdater.addKeywordUpdate(
                agentName, keywords, key, value, operation
            )

    def addInteractionCounter(
        self, agentName: str, key: str = "interactionCount"
    ) -> None:
        """Add an interaction counter for an agent.

        Args:
            agentName: Agent name.
            key: State key for the counter.
        """
        self._stateUpdater.addInteractionCounter(agentName, key)

    def addStateUpdateCallback(
        self,
        agentName: str,
        callback: Callable[
            [str, str, str, dict[str, Any]], dict[str, Any]
        ],
    ) -> None:
        """Add a callback for dynamic state updates.

        Args:
            agentName: Agent name.
            callback: Function(agentName, input, response, state) -> updates.
        """
        self._stateUpdater.addCallback(agentName, callback)

    def enableAutoStateUpdates(self) -> None:
        """Enable automatic state updates after interactions."""
        self._autoApplyStateUpdates = True

    def disableAutoStateUpdates(self) -> None:
        """Disable automatic state updates after interactions."""
        self._autoApplyStateUpdates = False

    @property
    def stateUpdater(self) -> AgentStateUpdater:
        """Get the state updater for advanced configuration."""
        return self._stateUpdater

    # World State Management

    def setWorldState(self, state: dict[str, Any]) -> None:
        """Set the world state.

        Args:
            state: New world state dictionary.
        """
        self._worldState = state.copy()
        self._storage.saveState("current", self._worldState)
        logger.debug("World state updated")

    def updateWorldState(self, updates: dict[str, Any]) -> None:
        """Update world state with new values.

        Args:
            updates: Values to merge into world state.
        """
        self._worldState.update(updates)
        self._storage.saveState("current", self._worldState)

    def getWorldState(self) -> dict[str, Any]:
        """Get current world state."""
        return self._worldState.copy()

    def queryState(self, *keys: str) -> dict[str, Any]:
        """Query specific state values.

        Args:
            *keys: State keys to retrieve.

        Returns:
            Dictionary with requested key-value pairs.
        """
        if not keys:
            return self._worldState.copy()

        return {k: self._worldState.get(k) for k in keys if k in self._worldState}

    def getStateValue(self, key: str, default: Any = None) -> Any:
        """Get a single state value.

        Args:
            key: State key to retrieve.
            default: Default value if key doesn't exist.

        Returns:
            The state value or default.
        """
        return self._worldState.get(key, default)

    def hasStateKey(self, key: str) -> bool:
        """Check if a state key exists.

        Args:
            key: State key to check.

        Returns:
            True if key exists in world state.
        """
        return key in self._worldState

    def getHistory(self) -> list[Any]:
        """Get interaction history from the current session.

        Returns:
            List of interaction records with agentName, userInput, response.
        """
        if not self._sessionRecorder.isRecording:
            return []
        return self._sessionRecorder.getInteractions()

    def getStateBucket(self) -> str:
        """Get the current state bucket for signature matching.

        Returns:
            Bucketed state string.
        """
        return self._stateBucketer.bucketState(self._worldState)

    def compareStates(
        self, checkpointName: str | None = None
    ) -> dict[str, dict[str, Any]]:
        """Compare current state with a checkpoint or initial state.

        Args:
            checkpointName: Checkpoint to compare with (None for initial).

        Returns:
            Dict with 'added', 'removed', 'changed' keys.
        """
        if checkpointName:
            checkpoint = self._checkpointManager.load(checkpointName)
            previousState = checkpoint.worldState
        else:
            previousState = {}

        current = self._worldState
        added = {k: v for k, v in current.items() if k not in previousState}
        removed = {k: v for k, v in previousState.items() if k not in current}
        changed = {
            k: {"from": previousState[k], "to": current[k]}
            for k in current
            if k in previousState and current[k] != previousState[k]
        }

        return {"added": added, "removed": removed, "changed": changed}

    # Interaction Methods

    def interact(
        self,
        agentName: str,
        userInput: str,
        situationType: str = "general",
        context: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Interact with a specific agent.

        Args:
            agentName: Name of the agent to interact with.
            userInput: User's input message.
            situationType: Type of situation for signature matching.
            context: Additional context for the interaction.

        Returns:
            Agent's response.

        Raises:
            AgentNotFoundError: If agent not found.
            CostLimitError: If cost limit would be exceeded.
            RuleViolationError: If a rule is violated (in strict mode).
        """
        agent = self.getAgent(agentName)
        context = context or {}

        # Start performance tracking
        self._performanceTracker.startTimer(agentName)

        # Check cost limit before proceeding
        self._checkCostLimit()

        # Check rules
        violations = self._rules.checkInteraction(
            agentName=agentName,
            userInput=userInput,
            state=self._worldState,
            turnCount=self._turnCount,
        )
        if violations and self._rules.strictMode:
            v = violations[0]
            raise RuleViolationError(v.ruleName, v.message)

        # Compute signature for cache lookup
        stateBucket = self._stateBucketer.bucketState(self._worldState)
        signature = computeSignature(
            SignatureComponents(
                agentName=agentName,
                situationType=situationType,
                stateBucket=stateBucket,
                inputIntent=self._extractIntent(userInput),
            )
        )

        # Check cache first
        if self._responseCache:
            cachedResponse = self._responseCache.get(signature)
            if cachedResponse:
                logger.info(f"Cache hit for {agentName}")
                if self._costTracker:
                    self._costTracker.recordCacheHit()

                # Record cached interaction
                if self._recordingEnabled:
                    self._sessionRecorder.recordInteraction(
                        agentName=agentName,
                        userInput=userInput,
                        response=cachedResponse.response,
                        situationType=situationType,
                        fromCache=True,
                        worldState=self._worldState.copy(),
                    )

                # Apply state updates for cached response
                if self._autoApplyStateUpdates:
                    self._applyStateUpdates(agentName, userInput, cachedResponse.response)

                # Record performance metrics for cache hit
                self._performanceTracker.stopTimer(
                    cost=0.0,
                    inputTokens=0,
                    outputTokens=0,
                    fromCache=True,
                    model=agent.model,
                )

                self._turnCount += 1
                return AgentResponse(
                    agentName=agentName,
                    content=cachedResponse.response,
                    fromCache=True,
                    metadata={"signature": signature, "situationType": situationType},
                )

        # Build messages with memory management
        messages = self._buildMessages(agent, userInput, context)

        # Check token budget
        estimatedTokens = self._tokenBudgetManager.estimateMessagesTokens(messages)
        estimatedTokens += self._tokenBudgetManager.estimateTokens(agent.systemPrompt)
        budgetCheck = self._tokenBudgetManager.checkBudget(estimatedTokens)

        if not budgetCheck["allowed"]:
            if budgetCheck["needsCompaction"]:
                # Compact messages to fit budget
                logger.warning(f"Token budget exceeded, compacting: {budgetCheck['reason']}")
                messages = self._llmClient.compact(messages)
            else:
                raise CostLimitError(
                    limit=budgetCheck["usage"]["budgetRemaining"],
                    current=budgetCheck["usage"]["totalTokens"],
                    requested=estimatedTokens,
                )

        if budgetCheck.get("warning"):
            logger.warning(f"Token budget warning: {budgetCheck['reason']}")

        # Generate response via LLM
        llmResponse = self._llmClient.generateAgentResponse(
            agentSystemPrompt=agent.systemPrompt,
            messages=messages,
            model=agent.model,
        )

        content = llmResponse["content"]

        # Record token usage
        usage = llmResponse.get("usage", {})
        self._tokenBudgetManager.recordUsage(
            inputTokens=usage.get("inputTokens", 0),
            outputTokens=usage.get("outputTokens", 0),
        )

        # Cache the response
        if self._responseCache:
            self._responseCache.put(CachedResponse(signature=signature, response=content))

        response = AgentResponse(
            agentName=agentName,
            content=content,
            fromCache=False,
            model=llmResponse["model"],
            usage=llmResponse["usage"],
            metadata={"signature": signature, "situationType": situationType},
        )

        # Record the interaction
        if self._recordingEnabled:
            self._sessionRecorder.recordInteraction(
                agentName=agentName,
                userInput=userInput,
                response=content,
                situationType=situationType,
                fromCache=False,
                model=llmResponse["model"],
                usage=llmResponse["usage"],
                worldState=self._worldState.copy(),
            )

        # Apply state updates
        if self._autoApplyStateUpdates:
            self._applyStateUpdates(agentName, userInput, content)

        # Record performance metrics for LLM response
        interactionCost = 0.0
        if self._costTracker:
            stats = self._costTracker.getStats()
            # Calculate cost from last interaction
            interactionCost = stats.get("lastInteractionCost", 0.0)

        self._performanceTracker.stopTimer(
            cost=interactionCost,
            inputTokens=usage.get("inputTokens", 0),
            outputTokens=usage.get("outputTokens", 0),
            fromCache=False,
            model=llmResponse["model"],
        )

        # Increment turn count
        self._turnCount += 1

        logger.info(f"Generated response for {agentName}")
        return response

    def _applyStateUpdates(
        self, agentName: str, userInput: str, response: str
    ) -> None:
        """Apply state updates from an interaction.

        Args:
            agentName: Agent that responded.
            userInput: User's input.
            response: Agent's response.
        """
        if not self._stateUpdater.hasRules(agentName):
            return

        updates = self._stateUpdater.processInteraction(
            agentName, userInput, response, self._worldState
        )

        if updates:
            newState = self._stateUpdater.applyUpdates(updates, self._worldState)
            self._worldState = newState
            self._storage.saveState("current", self._worldState)
            logger.debug(f"Applied state updates from {agentName}: {list(updates.keys())}")

    def _checkCostLimit(self) -> None:
        """Check if cost limit would be exceeded.

        Raises:
            CostLimitError: If cost limit exceeded.
        """
        if self._maxCost is None or self._costTracker is None:
            return

        stats = self._costTracker.getStats()
        if stats["totalCost"] >= self._maxCost:
            raise CostLimitError(
                limit=self._maxCost,
                current=stats["totalCost"],
                requested=0,
            )

    def _buildMessages(
        self,
        agent: AgentConfig,
        userInput: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Build message list for LLM call.

        Args:
            agent: Agent configuration.
            userInput: User's input.
            context: Additional context.

        Returns:
            List of messages for the LLM.
        """
        messages: list[dict[str, Any]] = []

        # Add context as system information if provided
        if context:
            contextStr = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages.append(
                {
                    "role": "user",
                    "content": f"[Context: {contextStr}]",
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "I understand the context. How can I help?",
                }
            )

        # Add user input
        messages.append({"role": "user", "content": userInput})

        return messages

    def _extractIntent(self, userInput: str) -> str:
        """Extract intent from user input for signature matching.

        Simple extraction - takes first 50 chars normalized.
        Can be enhanced with more sophisticated NLP.

        Args:
            userInput: User's input text.

        Returns:
            Intent string for signature.
        """
        # Simple normalization for now
        normalized = userInput.lower().strip()[:50]
        return normalized

    # Checkpoint Management

    def saveCheckpoint(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        """Save a checkpoint of current state.

        Args:
            name: Checkpoint name.
            metadata: Additional metadata.
        """
        agentStates = {
            agentName: agent.model_dump() for agentName, agent in self._agents.items()
        }

        self._checkpointManager.save(
            name=name,
            worldState=self._worldState,
            agentStates=agentStates,
            metadata=metadata,
        )
        logger.info(f"Saved checkpoint: {name}")

    def loadCheckpoint(self, name: str) -> None:
        """Load a checkpoint.

        Args:
            name: Checkpoint name to load.
        """
        checkpoint = self._checkpointManager.load(name)

        # Restore world state
        self._worldState = checkpoint.worldState

        # Restore agents
        self._agents.clear()
        for agentName, agentData in checkpoint.agentStates.items():
            config = AgentConfig.model_validate(agentData)
            self._agents[agentName] = config

        logger.info(f"Loaded checkpoint: {name}")

    def listCheckpoints(self) -> list[str]:
        """List available checkpoints."""
        return self._checkpointManager.list()

    # =========================================================================
    # Simulation Save/Resume (FR28)
    # =========================================================================

    def saveSimulation(self, name: str | None = None) -> str:
        """Save complete simulation state for later resumption.

        Saves all state needed to fully resume the simulation later,
        including agents, world state, turn count, history, and metrics.

        Args:
            name: Optional save name (defaults to "autosave").

        Returns:
            Name of the save.

        Example:
            >>> sim.interact("agent", "Hello")
            >>> saveName = sim.saveSimulation("my_save")
            >>> # Later...
            >>> sim2 = Simulation.loadSimulation("my_sim", saveName, dbPath)
        """
        saveName = name or "autosave"

        # Collect complete simulation state
        simulationState = {
            "version": "1.0",
            "simulationName": self.name,
            "turnCount": self._turnCount,
            "worldState": self._worldState,
            "agents": {
                agentName: agent.model_dump()
                for agentName, agent in self._agents.items()
            },
            "history": self._history,
            "costStats": self._costTracker.getStats() if self._costTracker else None,
            "tokenBudgetUsage": self._tokenBudgetManager.getUsage(),
            "testMode": self._testMode,
        }

        # Save as a special checkpoint with full state
        self._checkpointManager.save(
            name=f"__save__{saveName}",
            worldState=self._worldState,
            agentStates={
                name: agent.model_dump() for name, agent in self._agents.items()
            },
            metadata=simulationState,
        )

        logger.info(f"Saved simulation state: {saveName}")
        return saveName

    def resumeSimulation(self, saveName: str) -> None:
        """Resume simulation from a saved state.

        Restores all state from a previous save, allowing the simulation
        to continue exactly where it left off.

        Args:
            saveName: Name of the save to resume from.

        Raises:
            SessionNotFoundError: If save doesn't exist.
        """
        checkpoint = self._checkpointManager.load(f"__save__{saveName}")
        state = checkpoint.metadata

        # Restore turn count
        self._turnCount = state.get("turnCount", 0)

        # Restore world state
        self._worldState = checkpoint.worldState

        # Restore agents
        self._agents.clear()
        for agentName, agentData in checkpoint.agentStates.items():
            config = AgentConfig.model_validate(agentData)
            self._agents[agentName] = config

        # Restore history
        self._history = state.get("history", [])

        logger.info(f"Resumed simulation from: {saveName}")

    def listSaves(self) -> list[str]:
        """List available simulation saves.

        Returns:
            List of save names.
        """
        allCheckpoints = self._checkpointManager.list()
        saves = [
            cp.replace("__save__", "")
            for cp in allCheckpoints
            if cp.startswith("__save__")
        ]
        return saves

    def deleteSave(self, saveName: str) -> None:
        """Delete a simulation save.

        Args:
            saveName: Name of save to delete.
        """
        self._checkpointManager.delete(f"__save__{saveName}")
        logger.info(f"Deleted save: {saveName}")

    def hasSave(self, saveName: str) -> bool:
        """Check if a save exists.

        Args:
            saveName: Name of save to check.

        Returns:
            True if save exists.
        """
        return self._checkpointManager.exists(f"__save__{saveName}")

    @classmethod
    def resumeFrom(
        cls,
        simulationName: str,
        saveName: str,
        dbPath: Path | None = None,
    ) -> "Simulation":
        """Create a new simulation instance and resume from saved state.

        Factory method to create a simulation and immediately resume
        from a previously saved state.

        Args:
            simulationName: Name of the simulation.
            saveName: Name of the save to resume from.
            dbPath: Database path (uses default if not specified).

        Returns:
            Simulation instance with restored state.

        Example:
            >>> sim = Simulation.resumeFrom("my_sim", "autosave")
            >>> sim.interact("agent", "Continue our conversation")
        """
        sim = cls(name=simulationName, dbPath=dbPath)
        sim.resumeSimulation(saveName)
        return sim

    # Statistics and Cost Tracking

    def getStats(self) -> dict[str, Any]:
        """Get simulation statistics including costs.

        Returns:
            Dictionary with simulation stats.
        """
        stats: dict[str, Any] = {
            "name": self.name,
            "agentCount": len(self._agents),
            "agents": self.listAgents(),
            "turnCount": self._turnCount,
            "historyLength": len(self._history),
            "checkpointCount": len(self.listCheckpoints()),
        }

        if self._costTracker:
            stats["costs"] = self._costTracker.getStats()

        if self._responseCache:
            stats["cache"] = self._responseCache.getStats()

        stats["tokenBudget"] = self._tokenBudgetManager.getUsage()

        if self._maxCost is not None:
            costStats = stats.get("costs", {})
            stats["costLimit"] = {
                "limit": self._maxCost,
                "current": costStats.get("totalCost", 0),
                "remaining": self._maxCost - costStats.get("totalCost", 0),
            }

        stats["rules"] = {
            "count": len(self._rules.listRules()),
            "violations": len(self._rules.getViolations()),
            "strictMode": self._rules.strictMode,
        }

        return stats

    def getTokenUsage(self) -> dict[str, Any]:
        """Get current token usage.

        Returns:
            Dictionary with token usage stats.
        """
        return self._tokenBudgetManager.getUsage()

    def resetCosts(self) -> None:
        """Reset cost tracking statistics."""
        if self._costTracker:
            self._costTracker.reset()
        self._tokenBudgetManager.reset()

    # Cost Estimation

    def estimateInteractionCost(
        self,
        agentName: str | None = None,
        inputText: str | None = None,
    ) -> CostEstimate:
        """Estimate cost for a single interaction.

        Args:
            agentName: Agent name (for model-specific estimates).
            inputText: User input text (for token estimation).

        Returns:
            CostEstimate with estimated cost.
        """
        model = None
        systemPromptLength = None

        if agentName and agentName in self._agents:
            agent = self._agents[agentName]
            model = agent.model
            systemPromptLength = len(agent.systemPrompt)

        return self._costEstimator.estimateInteraction(
            inputText=inputText,
            agentName=agentName,
            model=model,
            systemPromptLength=systemPromptLength,
        )

    def estimateSessionCost(
        self, turns: int, agentCount: int | None = None
    ) -> CostEstimate:
        """Estimate cost for a simulation session.

        Args:
            turns: Number of turns to estimate.
            agentCount: Number of agents (defaults to registered count).

        Returns:
            CostEstimate for the session.
        """
        if agentCount is None:
            agentCount = len(self._agents)

        return self._costEstimator.estimateSession(turns, agentCount)

    def estimateReplayCost(self, sessionId: str) -> CostEstimate:
        """Estimate cost to replay a session.

        Args:
            sessionId: Session to replay.

        Returns:
            CostEstimate for replay.
        """
        sessionData = self._sessionRecorder.loadSession(sessionId)
        return self._costEstimator.estimateReplay(sessionData)

    def getRemainingBudget(self) -> dict[str, Any] | None:
        """Get remaining budget information.

        Returns:
            Budget info dict if cost limit is set, None otherwise.
        """
        if self._maxCost is None:
            return None

        currentCost = 0.0
        if self._costTracker:
            currentCost = self._costTracker.getStats().get("totalCost", 0.0)

        return self._costEstimator.getRemainingBudget(self._maxCost, currentCost)

    def willExceedBudget(
        self, estimate: CostEstimate | None = None, interactions: int = 1
    ) -> bool:
        """Check if an operation would exceed the cost limit.

        Args:
            estimate: Cost estimate (or None to estimate interactions).
            interactions: Number of interactions to estimate.

        Returns:
            True if limit would be exceeded.
        """
        if self._maxCost is None:
            return False

        currentCost = 0.0
        if self._costTracker:
            currentCost = self._costTracker.getStats().get("totalCost", 0.0)

        if estimate is None:
            estimate = self._costEstimator.estimateBatch(interactions)

        return self._costEstimator.willExceedLimit(estimate, self._maxCost, currentCost)

    @property
    def costEstimator(self) -> CostEstimator:
        """Get the cost estimator for advanced configuration."""
        return self._costEstimator

    # =========================================================================
    # Data Export (FR29)
    # =========================================================================

    def exportToFile(
        self,
        filePath: Path | str,
        format: str = "json",
        includeHistory: bool = True,
        includeStats: bool = True,
        includeCosts: bool = True,
        includeAgents: bool = True,
    ) -> Path:
        """Export current simulation data to file for external analysis.

        Exports comprehensive simulation data including conversation history,
        agent configurations, costs, and statistics in various formats.

        Args:
            filePath: Path to write export file.
            format: Export format ("json" or "csv").
            includeHistory: Include conversation history.
            includeStats: Include statistics.
            includeCosts: Include cost data.
            includeAgents: Include agent configurations.

        Returns:
            Path to the exported file.

        Example:
            >>> sim.exportToFile("analysis/session.json")
            >>> sim.exportToFile("analysis/history.csv", format="csv")
        """
        import csv

        filePath = Path(filePath)
        filePath.parent.mkdir(parents=True, exist_ok=True)

        exportData: dict[str, Any] = {
            "simulationName": self.name,
            "exportedAt": datetime.now().isoformat(),
            "turnCount": self._turnCount,
        }

        if includeHistory:
            exportData["history"] = self._history

        if includeStats:
            exportData["stats"] = self.getStats()

        if includeCosts and self._costTracker:
            exportData["costs"] = self._costTracker.getStats()
            exportData["tokenUsage"] = self._tokenBudgetManager.getUsage()

        if includeAgents:
            exportData["agents"] = {
                name: agent.model_dump()
                for name, agent in self._agents.items()
            }

        exportData["worldState"] = self._worldState

        if format == "json":
            with open(filePath, "w", encoding="utf-8") as f:
                json.dump(exportData, f, indent=2, ensure_ascii=False, default=str)

        elif format == "csv":
            # CSV exports history as rows
            with open(filePath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "turn", "agent", "role", "content", "timestamp",
                    "inputTokens", "outputTokens", "cached"
                ])
                for entry in self._history:
                    writer.writerow([
                        entry.get("turn", ""),
                        entry.get("agentName", ""),
                        entry.get("agentRole", ""),
                        entry.get("content", ""),
                        entry.get("timestamp", ""),
                        entry.get("inputTokens", ""),
                        entry.get("outputTokens", ""),
                        entry.get("cached", False),
                    ])
        else:
            raise ValueError(f"Unsupported export format: {format}")

        logger.info(f"Exported session to {filePath}")
        return filePath

    def exportHistory(
        self,
        filePath: Path | str,
        agentFilter: str | list[str] | None = None,
        format: str = "json",
    ) -> Path:
        """Export conversation history.

        Args:
            filePath: Path to write export file.
            agentFilter: Optional agent(s) to filter by.
            format: Export format ("json" or "csv").

        Returns:
            Path to the exported file.

        Example:
            >>> sim.exportHistory("history.json", agentFilter="pm")
        """
        import csv

        filePath = Path(filePath)
        filePath.parent.mkdir(parents=True, exist_ok=True)

        history = self._history

        # Apply agent filter
        if agentFilter:
            if isinstance(agentFilter, str):
                agentFilter = [agentFilter]
            history = [
                entry for entry in history
                if entry.get("agentName") in agentFilter
            ]

        if format == "json":
            with open(filePath, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False, default=str)

        elif format == "csv":
            with open(filePath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "turn", "agent", "prompt", "response", "timestamp"
                ])
                for entry in history:
                    writer.writerow([
                        entry.get("turn", ""),
                        entry.get("agentName", ""),
                        entry.get("prompt", ""),
                        entry.get("content", ""),
                        entry.get("timestamp", ""),
                    ])
        else:
            raise ValueError(f"Unsupported export format: {format}")

        logger.info(f"Exported history to {filePath}")
        return filePath

    def exportCostReport(
        self,
        filePath: Path | str,
        format: str = "json",
    ) -> Path:
        """Export detailed cost report.

        Args:
            filePath: Path to write export file.
            format: Export format ("json" or "csv").

        Returns:
            Path to the exported file.
        """
        import csv

        filePath = Path(filePath)
        filePath.parent.mkdir(parents=True, exist_ok=True)

        reportData: dict[str, Any] = {
            "simulationName": self.name,
            "exportedAt": datetime.now().isoformat(),
        }

        if self._costTracker:
            costStats = self._costTracker.getStats()
            reportData["summary"] = {
                "totalCost": costStats.get("totalCost", 0),
                "totalInputTokens": costStats.get("totalInputTokens", 0),
                "totalOutputTokens": costStats.get("totalOutputTokens", 0),
                "totalCachedTokens": costStats.get("totalCachedTokens", 0),
                "totalInteractions": costStats.get("interactionCount", 0),
            }
            reportData["byModel"] = costStats.get("byModel", {})
            reportData["byAgent"] = costStats.get("byAgent", {})
        else:
            reportData["summary"] = {"message": "Cost tracking not enabled"}

        reportData["tokenBudget"] = self._tokenBudgetManager.getUsage()

        if self._maxCost:
            remaining = self.getRemainingBudget()
            reportData["budgetLimit"] = {
                "limit": self._maxCost,
                "remaining": remaining,
            }

        if format == "json":
            with open(filePath, "w", encoding="utf-8") as f:
                json.dump(reportData, f, indent=2, ensure_ascii=False, default=str)

        elif format == "csv":
            with open(filePath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["metric", "value"])
                summary = reportData.get("summary", {})
                for key, value in summary.items():
                    writer.writerow([key, value])
        else:
            raise ValueError(f"Unsupported export format: {format}")

        logger.info(f"Exported cost report to {filePath}")
        return filePath

    def getExportableData(self) -> dict[str, Any]:
        """Get all session data as a dictionary for custom export.

        Returns:
            Dictionary containing all exportable session data.
        """
        return {
            "simulationName": self.name,
            "turnCount": self._turnCount,
            "history": self._history,
            "worldState": self._worldState,
            "agents": {
                name: agent.model_dump()
                for name, agent in self._agents.items()
            },
            "stats": self.getStats(),
            "costs": self._costTracker.getStats() if self._costTracker else None,
            "tokenUsage": self._tokenBudgetManager.getUsage(),
        }

    # Lifecycle

    def start(self, sessionId: str | None = None) -> str:
        """Start the simulation and begin recording.

        Args:
            sessionId: Optional custom session ID.

        Returns:
            The session ID.
        """
        self._isRunning = True
        session = self._sessionRecorder.startSession(sessionId)
        logger.info(f"Simulation '{self.name}' started, session: {session}")
        return session

    def stop(self) -> None:
        """Stop the simulation and end recording."""
        self._isRunning = False

        # End session with cost data
        totalCost = 0.0
        if self._costTracker:
            totalCost = self._costTracker.getStats().get("totalCost", 0.0)

        self._sessionRecorder.endSession(totalCost=totalCost)
        logger.info(f"Simulation '{self.name}' stopped")

    @property
    def isRunning(self) -> bool:
        """Check if simulation is running."""
        return self._isRunning

    # Session Management

    def enableRecording(self) -> None:
        """Enable interaction recording."""
        self._recordingEnabled = True

    def disableRecording(self) -> None:
        """Disable interaction recording."""
        self._recordingEnabled = False

    @property
    def isRecording(self) -> bool:
        """Check if recording is enabled."""
        return self._recordingEnabled and self._sessionRecorder.isRecording

    def listSessions(self) -> list[dict[str, Any]]:
        """List all recorded sessions.

        Returns:
            List of session metadata.
        """
        return self._sessionRecorder.listSessions()

    def loadSession(self, sessionId: str) -> dict[str, Any]:
        """Load a recorded session.

        Args:
            sessionId: Session ID to load.

        Returns:
            Session data with metadata and interactions.
        """
        return self._sessionRecorder.loadSession(sessionId)

    def exportSession(self, sessionId: str, format: str = "json") -> str:
        """Export a session.

        Args:
            sessionId: Session ID to export.
            format: Export format ('json' or 'jsonl').

        Returns:
            Exported data as string.
        """
        return self._sessionRecorder.exportSession(sessionId, format)

    def getSessionStats(self, sessionId: str) -> dict[str, Any]:
        """Get statistics for a session.

        Args:
            sessionId: Session ID.

        Returns:
            Session statistics.
        """
        return self._sessionRecorder.getSessionStats(sessionId)

    # Session Replay

    def createReplayer(self, sessionId: str) -> SessionReplayer:
        """Create a replayer for a recorded session.

        Args:
            sessionId: Session ID to replay.

        Returns:
            SessionReplayer instance.
        """
        replayer = SessionReplayer(self._dbPath, self.name)
        replayer.loadSession(sessionId)
        return replayer

    def replaySession(self, sessionId: str) -> list[dict[str, Any]]:
        """Replay a session and return all interactions.

        Args:
            sessionId: Session ID to replay.

        Returns:
            List of interaction dicts.
        """
        replayer = self.createReplayer(sessionId)
        return [
            {
                "index": i.index,
                "agentName": i.agentName,
                "userInput": i.userInput,
                "response": i.response,
                "fromCache": i.fromCache,
            }
            for i in replayer.iterate()
        ]

    def verifySession(
        self,
        sessionId: str,
        driftThreshold: float = 0.0,
        agentFilter: str | list[str] | None = None,
    ) -> ReplayVerificationResult:
        """Verify a session by replaying and comparing responses.

        Replays a recorded session, regenerating responses for each
        interaction, and compares them to the original responses.
        Useful for detecting behavioral drift or validating consistency.

        Args:
            sessionId: Session ID to verify.
            driftThreshold: Allowed percentage of drifted responses (0.0-1.0).
                           0.0 means all responses must match exactly.
            agentFilter: Only verify specific agent(s).

        Returns:
            ReplayVerificationResult with detailed comparison.

        Example:
            >>> result = sim.verifySession("session123")
            >>> if result.passed:
            ...     print("Behavior is consistent!")
            ... else:
            ...     for drift in result.getDriftedInteractions():
            ...         print(f"Drift at {drift.index}: {drift.agentName}")
        """
        from pm6.state.sessionReplayer import ReplayVerifier

        replayer = SessionReplayer(self._dbPath, self.name)

        def generateResponse(
            agentName: str, userInput: str, worldState: dict[str, Any] | None
        ) -> str:
            """Generate a response for comparison."""
            # Temporarily set world state if provided
            originalState = self._worldState.copy()
            if worldState:
                self._worldState = worldState

            try:
                response = self.interact(agentName, userInput)
                return response.content
            finally:
                # Restore original state
                self._worldState = originalState

        verifier = ReplayVerifier(replayer, generateResponse)
        return verifier.verify(
            sessionId=sessionId,
            driftThreshold=driftThreshold,
            agentFilter=agentFilter,
        )

    def branchFromSession(
        self, sessionId: str, atIndex: int, newSessionId: str | None = None
    ) -> str:
        """Branch from a recorded session at a specific point.

        Restores world state from that point and starts a new session.

        Args:
            sessionId: Session to branch from.
            atIndex: Interaction index to branch from.
            newSessionId: Optional ID for new session.

        Returns:
            New session ID.
        """
        replayer = self.createReplayer(sessionId)
        branchData = replayer.branchFrom(atIndex)

        # Restore world state
        self._worldState = branchData["worldState"]

        # Reset turn count to branch point
        self._turnCount = atIndex + 1

        # Start new session
        return self.start(newSessionId)

    # Rules Management

    @property
    def rules(self) -> SimulationRules:
        """Get the simulation rules manager."""
        return self._rules

    @property
    def turnCount(self) -> int:
        """Get the current turn count."""
        return self._turnCount

    def resetTurnCount(self) -> None:
        """Reset the turn counter."""
        self._turnCount = 0

    # Test Mode Methods

    @property
    def isTestMode(self) -> bool:
        """Check if simulation is in test mode."""
        return self._testMode

    @property
    def mockClient(self) -> MockAnthropicClient | None:
        """Get the mock client (only available in test mode).

        Returns:
            MockAnthropicClient if in test mode, None otherwise.
        """
        return self._mockClient

    def setMockResponse(self, response: str) -> None:
        """Set a static mock response (test mode only).

        Args:
            response: Response content to return.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("setMockResponse requires test mode")
        from pm6.testing import MockResponse

        self._mockClient.setStaticResponse(MockResponse(content=response))

    def addMockResponse(self, response: str) -> None:
        """Add a mock response to the queue (test mode only).

        Args:
            response: Response content to add.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("addMockResponse requires test mode")
        from pm6.testing import MockResponse

        self._mockClient.addResponse(MockResponse(content=response))

    def addMockResponses(self, responses: list[str]) -> None:
        """Add multiple mock responses (test mode only).

        Args:
            responses: List of response contents to add.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("addMockResponses requires test mode")
        for r in responses:
            self.addMockResponse(r)

    def addAgentMockResponse(self, agentName: str, response: str) -> None:
        """Add a mock response for a specific agent (test mode only).

        Args:
            agentName: Agent name.
            response: Response content.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("addAgentMockResponse requires test mode")
        from pm6.testing import MockResponse

        self._mockClient.addAgentResponse(agentName, MockResponse(content=response))

    def getMockCallCount(self) -> int:
        """Get the number of mock LLM calls made (test mode only).

        Returns:
            Number of calls made.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("getMockCallCount requires test mode")
        return self._mockClient.callCount

    def getMockCallHistory(self) -> list[dict[str, Any]]:
        """Get the mock call history (test mode only).

        Returns:
            List of call records.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("getMockCallHistory requires test mode")
        return self._mockClient.callHistory

    def resetMockState(self) -> None:
        """Reset mock state for fresh testing (test mode only).

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode or self._mockClient is None:
            raise SimulationError("resetMockState requires test mode")
        self._mockClient.reset()

    @classmethod
    def createTestSimulation(
        cls,
        name: str = "test_simulation",
        responses: list[str] | None = None,
        worldState: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "Simulation":
        """Factory method to create a test simulation.

        Convenience method for creating properly configured test simulations.

        Args:
            name: Simulation name.
            responses: List of mock responses to queue.
            worldState: Initial world state.
            **kwargs: Additional Simulation arguments.

        Returns:
            Configured test Simulation instance.
        """
        sim = cls(name=name, testMode=True, **kwargs)
        if worldState:
            sim.setWorldState(worldState)
        if responses:
            sim.addMockResponses(responses)
        return sim

    # Agent Validation Methods (FR41, FR45)

    def createValidator(self, strictMode: bool = False) -> "AgentValidator":
        """Create an agent validator for response validation.

        Args:
            strictMode: If True, warnings become errors.

        Returns:
            AgentValidator instance.
        """
        from pm6.testing import AgentValidator

        return AgentValidator(strictMode=strictMode)

    def validateResponse(
        self,
        agentName: str,
        response: str,
        validator: "AgentValidator | None" = None,
        context: dict[str, Any] | None = None,
    ) -> "ValidationReport":
        """Validate an agent response against rules.

        Args:
            agentName: Agent that produced the response.
            response: Response text to validate.
            validator: Validator to use (creates default if None).
            context: Additional context (world state added automatically).

        Returns:
            ValidationReport with results.
        """
        from pm6.testing import AgentValidator, ValidationReport

        if validator is None:
            validator = AgentValidator()

        ctx = {"worldState": self._worldState.copy()}
        if context:
            ctx.update(context)

        return validator.validate(agentName, response, ctx)

    def createComparator(self) -> "AgentComparator":
        """Create an agent comparator for comparing configurations.

        Returns:
            AgentComparator instance.
        """
        from pm6.testing import AgentComparator

        return AgentComparator()

    def compareResponses(
        self,
        configA: str,
        responseA: str,
        configB: str,
        responseB: str,
        comparator: "AgentComparator | None" = None,
    ) -> dict[str, Any]:
        """Compare two agent responses.

        Args:
            configA: Name of first configuration.
            responseA: Response from first configuration.
            configB: Name of second configuration.
            responseB: Response from second configuration.
            comparator: Comparator to use (creates default if None).

        Returns:
            Comparison result dictionary.
        """
        from pm6.testing import AgentComparator

        if comparator is None:
            comparator = AgentComparator()

        result = comparator.compare(configA, responseA, configB, responseB)
        return result.toDict()

    # Scenario Testing Methods (FR47)

    def createScenarioTester(self) -> "ScenarioTester":
        """Create a scenario tester for automated testing.

        Returns:
            ScenarioTester instance configured for this simulation.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode:
            raise SimulationError("createScenarioTester requires test mode")

        from pm6.testing import ScenarioTester

        return ScenarioTester(self)

    def runScenario(
        self,
        scenario: Any,
    ) -> dict[str, Any]:
        """Run a single test scenario.

        Args:
            scenario: TestScenario to run.

        Returns:
            ScenarioResult as dictionary.

        Raises:
            SimulationError: If not in test mode.
        """
        if not self._testMode:
            raise SimulationError("runScenario requires test mode")

        from pm6.testing import ScenarioTester

        tester = ScenarioTester(self)
        result = tester.runScenario(scenario)
        return result.toDict()

    # Performance Metrics Methods (NFR1-5)

    @property
    def performanceTracker(self) -> PerformanceTracker:
        """Get the performance tracker for advanced metrics access."""
        return self._performanceTracker

    def getPerformanceStats(self) -> dict[str, Any]:
        """Get current performance statistics.

        Returns:
            Dictionary with response times, costs, and cache rates.
        """
        return self._performanceTracker.getStats()

    def getAgentPerformance(self, agentName: str) -> dict[str, Any]:
        """Get performance statistics for a specific agent.

        Args:
            agentName: Agent name.

        Returns:
            Agent-specific performance metrics.
        """
        return self._performanceTracker.getAgentStats(agentName)

    def createPerformanceBaseline(self, name: str) -> dict[str, Any]:
        """Create a performance baseline from current metrics.

        Args:
            name: Name for the baseline (e.g., "v1.0").

        Returns:
            Baseline metrics dictionary.
        """
        baseline = self._performanceTracker.createBaseline(name)
        return baseline.toDict()

    def comparePerformance(self, baselineName: str) -> dict[str, Any]:
        """Compare current performance to a baseline.

        Args:
            baselineName: Name of baseline to compare against.

        Returns:
            Comparison with regression indicators.
        """
        return self._performanceTracker.compareToBaseline(baselineName)

    def hasPerformanceRegression(self, baselineName: str) -> bool:
        """Check if there's a performance regression.

        Args:
            baselineName: Baseline to compare against.

        Returns:
            True if regression detected.
        """
        return self._performanceTracker.hasRegression(baselineName)

    def getPerformanceReport(self) -> str:
        """Get a formatted performance report.

        Returns:
            Human-readable performance report.
        """
        return self._performanceTracker.formatReport()

    # =========================================================================
    # Tool Use (FR9, NFR8)
    # =========================================================================

    @property
    def toolRegistry(self) -> ToolRegistry:
        """Get the tool registry."""
        return self._toolRegistry

    def registerTool(self, tool: Tool) -> None:
        """Register a tool for agents to use.

        Args:
            tool: Tool to register.

        Example:
            >>> sim.registerTool(Tool(
            ...     name="get_weather",
            ...     description="Get weather for a location",
            ...     inputSchema={"type": "object", "properties": {...}},
            ...     handler=lambda x: {"temp": 72}
            ... ))
        """
        self._toolRegistry.register(tool)

    def registerToolFromFunction(
        self,
        name: str,
        description: str,
        handler: Callable[[dict[str, Any]], Any],
        parameters: dict[str, dict[str, Any]],
        required: list[str] | None = None,
    ) -> None:
        """Register a tool from a function.

        Convenience method for registering tools without creating Tool objects.

        Args:
            name: Tool name.
            description: Tool description.
            handler: Function to execute the tool.
            parameters: Parameter schemas.
            required: Required parameter names.

        Example:
            >>> sim.registerToolFromFunction(
            ...     name="lookup_user",
            ...     description="Look up a user by ID",
            ...     handler=lambda x: {"name": "John"},
            ...     parameters={"userId": {"type": "string"}},
            ...     required=["userId"]
            ... )
        """
        from pm6.tools.toolRegistry import createTool

        tool = createTool(
            name=name,
            description=description,
            parameters=parameters,
            required=required,
            handler=handler,
        )
        self._toolRegistry.register(tool)

    def unregisterTool(self, name: str) -> None:
        """Unregister a tool.

        Args:
            name: Name of tool to remove.
        """
        self._toolRegistry.unregister(name)

    def getRegisteredTools(self) -> list[str]:
        """Get names of all registered tools.

        Returns:
            List of tool names.
        """
        return self._toolRegistry.getToolNames()

    def hasTool(self, name: str) -> bool:
        """Check if a tool is registered.

        Args:
            name: Tool name.

        Returns:
            True if registered.
        """
        return self._toolRegistry.has(name)

    def executeTool(self, name: str, inputs: dict[str, Any]) -> ToolResult:
        """Execute a tool directly.

        Args:
            name: Tool name.
            inputs: Tool inputs.

        Returns:
            Tool execution result.
        """
        call = ToolCall(id=f"direct_{name}", name=name, inputs=inputs)
        return self._toolRegistry.execute(call)

    def getToolStats(self) -> dict[str, Any]:
        """Get tool execution statistics.

        Returns:
            Dictionary with tool usage stats.
        """
        return self._toolRegistry.getStats()

    # =========================================================================
    # Reliability & Transactions (NFR11-15)
    # =========================================================================

    def createSnapshot(self) -> "StateSnapshot":
        """Create a snapshot of current simulation state.

        Used for transaction rollback and crash recovery.

        Returns:
            StateSnapshot containing current state.
        """
        from pm6.reliability import StateSnapshot

        return StateSnapshot(
            timestamp=datetime.now(),
            worldState=self._worldState.copy(),
            agentStates={
                name: agent.model_dump()
                for name, agent in self._agents.items()
            },
            turnCount=self._turnCount,
            history=list(self._history),
        )

    def restoreSnapshot(self, snapshot: "StateSnapshot") -> None:
        """Restore simulation state from a snapshot.

        Args:
            snapshot: Snapshot to restore from.
        """
        self._worldState = snapshot.worldState.copy()
        self._agents.clear()
        for name, agentData in snapshot.agentStates.items():
            config = AgentConfig.model_validate(agentData)
            self._agents[name] = config
        self._turnCount = snapshot.turnCount
        self._history = list(snapshot.history)
        logger.info("Restored simulation state from snapshot")

    def createTransactionManager(self) -> "TransactionManager":
        """Create a transaction manager for atomic operations.

        Returns:
            TransactionManager configured for this simulation.

        Example:
            >>> manager = sim.createTransactionManager()
            >>> with manager.transaction() as tx:
            ...     sim.interact("pm", "What's the plan?")
            ...     sim.interact("chancellor", "Budget update?")
            ...     # If anything fails, state is automatically rolled back
        """
        from pm6.reliability import TransactionManager

        return TransactionManager(
            snapshotProvider=self.createSnapshot,
            stateRestorer=self.restoreSnapshot,
        )

    def executeAtomic(self, operation: Callable[[], Any]) -> Any:
        """Execute an operation atomically with automatic rollback.

        If the operation raises an exception, simulation state is
        rolled back to the state before the operation.

        Args:
            operation: Callable to execute.

        Returns:
            Result of the operation.

        Raises:
            Exception: If operation fails (after rollback).

        Example:
            >>> result = sim.executeAtomic(lambda: sim.interact("pm", "Hello"))
        """
        manager = self.createTransactionManager()
        return manager.execute(operation)

    def executeManyAtomic(
        self, operations: list[tuple[Callable[[], Any], str]]
    ) -> list[Any]:
        """Execute multiple operations in a single atomic transaction.

        All operations succeed or all are rolled back.

        Args:
            operations: List of (callable, description) tuples.

        Returns:
            List of results from each operation.

        Example:
            >>> results = sim.executeManyAtomic([
            ...     (lambda: sim.interact("pm", "Hello"), "greeting"),
            ...     (lambda: sim.interact("chancellor", "Budget?"), "budget"),
            ... ])
        """
        manager = self.createTransactionManager()
        return manager.executeMany(operations)

    def checkpoint(self) -> "StateSnapshot":
        """Create a manual checkpoint of current state.

        Useful for long-running sessions where you want restore points.

        Returns:
            StateSnapshot that can be restored later.
        """
        snapshot = self.createSnapshot()
        logger.info("Created manual checkpoint")
        return snapshot

    def restoreFromCheckpoint(self, snapshot: "StateSnapshot") -> None:
        """Restore state from a previously created checkpoint.

        Args:
            snapshot: Checkpoint to restore from.
        """
        self.restoreSnapshot(snapshot)
        logger.info("Restored from checkpoint")
