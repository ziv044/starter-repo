"""Pipeline executor for step-by-step simulation execution.

Provides n8n-style visibility into pipeline execution, allowing:
- Step-by-step execution
- Inspection of inputs/outputs at each step
- Dry-run mode without LLM calls
- Debug logging and tracing
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pm6.core.types import (
    Event,
    OrchestratorDecision,
    PipelineConfig,
    PipelineStep,
)

if TYPE_CHECKING:
    from pm6.core.engine import SimulationEngine

logger = logging.getLogger("pm6.core.pipeline")


class StepStatus(str, Enum):
    """Status of a pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    """Result of executing a single pipeline step.

    Attributes:
        stepName: Name of the step that was executed.
        status: Status of the step.
        inputs: Input data that was provided to the step.
        outputs: Output data produced by the step.
        duration: Time taken to execute the step in seconds.
        error: Error message if the step failed.
        timestamp: When the step was executed.
    """

    stepName: str
    status: StepStatus = StepStatus.PENDING
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stepName": self.stepName,
            "status": self.status.value,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "duration": self.duration,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PipelineExecutionResult:
    """Result of a full pipeline execution.

    Attributes:
        turnNumber: The turn number for this execution.
        steps: Results for each step.
        totalDuration: Total time for the entire pipeline.
        success: Whether all steps completed successfully.
        orchestratorDecision: The orchestrator's decision (if applicable).
    """

    turnNumber: int
    steps: list[StepResult] = field(default_factory=list)
    totalDuration: float = 0.0
    success: bool = True
    orchestratorDecision: OrchestratorDecision | None = None

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "turnNumber": self.turnNumber,
            "steps": [s.toDict() for s in self.steps],
            "totalDuration": self.totalDuration,
            "success": self.success,
            "orchestratorDecision": (
                self.orchestratorDecision.toDict()
                if self.orchestratorDecision
                else None
            ),
        }


class PipelineExecutor:
    """Execute pipeline steps with visibility into each step.

    Provides n8n-style debugging capabilities:
    - Execute steps one at a time
    - Inspect inputs/outputs at each step
    - Dry-run mode that simulates execution
    - Full execution history

    Example:
        >>> executor = PipelineExecutor(engine)
        >>> # Execute step by step
        >>> result = executor.executeStep(0)  # turn_start
        >>> print(result.outputs)
        >>> result = executor.executeStep(1)  # gather_events
        >>> # Or execute all at once
        >>> full_result = executor.executeAll()
    """

    def __init__(self, engine: SimulationEngine):
        """Initialize the pipeline executor.

        Args:
            engine: The simulation engine to execute against.
        """
        self._engine = engine
        self._currentStepIndex = 0
        self._stepResults: list[StepResult] = []
        self._executionHistory: list[PipelineExecutionResult] = []
        self._currentTurnEvents: list[Event] = []
        self._dryRunMode = False

    @property
    def pipelineConfig(self) -> PipelineConfig:
        """Get the pipeline configuration."""
        return self._engine.pipelineConfig

    @property
    def currentStepIndex(self) -> int:
        """Get the current step index."""
        return self._currentStepIndex

    @property
    def stepResults(self) -> list[StepResult]:
        """Get results of executed steps."""
        return self._stepResults.copy()

    @property
    def executionHistory(self) -> list[PipelineExecutionResult]:
        """Get full execution history."""
        return self._executionHistory.copy()

    def reset(self) -> None:
        """Reset the executor for a new turn."""
        self._currentStepIndex = 0
        self._stepResults = []
        self._currentTurnEvents = []

    def setDryRunMode(self, enabled: bool) -> None:
        """Enable or disable dry-run mode.

        In dry-run mode, no actual LLM calls are made.
        The executor shows what would happen without executing.

        Args:
            enabled: Whether to enable dry-run mode.
        """
        self._dryRunMode = enabled

    def executeStep(self, stepIndex: int | None = None) -> StepResult:
        """Execute a single pipeline step.

        Args:
            stepIndex: Index of the step to execute.
                       If None, executes the next pending step.

        Returns:
            Result of the step execution.
        """
        if stepIndex is None:
            stepIndex = self._currentStepIndex

        pipeline = self.pipelineConfig
        if stepIndex >= len(pipeline.steps):
            return StepResult(
                stepName="invalid",
                status=StepStatus.FAILED,
                error=f"Step index {stepIndex} out of range",
            )

        step = pipeline.steps[stepIndex]
        result = self._executeStepByType(step, stepIndex)

        # Store result
        while len(self._stepResults) <= stepIndex:
            self._stepResults.append(
                StepResult(stepName="pending", status=StepStatus.PENDING)
            )
        self._stepResults[stepIndex] = result

        # Advance to next step
        if stepIndex == self._currentStepIndex:
            self._currentStepIndex += 1

        return result

    def executeAll(self) -> PipelineExecutionResult:
        """Execute all pipeline steps for a complete turn.

        Returns:
            Complete execution result with all steps.
        """
        startTime = time.time()
        self.reset()

        pipeline = self.pipelineConfig
        turnNumber = self._engine.currentTurn + 1

        result = PipelineExecutionResult(turnNumber=turnNumber)

        for i, step in enumerate(pipeline.steps):
            stepResult = self.executeStep(i)
            result.steps.append(stepResult)

            if stepResult.status == StepStatus.FAILED:
                result.success = False
                break

        result.totalDuration = time.time() - startTime

        # Capture orchestrator decision if available
        result.orchestratorDecision = self._engine.lastOrchestratorDecision

        # Store in history
        self._executionHistory.append(result)

        return result

    def dryRun(self) -> PipelineExecutionResult:
        """Execute all steps in dry-run mode.

        Simulates execution without making actual LLM calls.
        Shows what would happen based on current state.

        Returns:
            Execution result with simulated outputs.
        """
        previousMode = self._dryRunMode
        self._dryRunMode = True
        try:
            return self.executeAll()
        finally:
            self._dryRunMode = previousMode

    def getStepPreview(self, stepIndex: int) -> dict[str, Any]:
        """Preview what a step would receive as input.

        Args:
            stepIndex: Index of the step to preview.

        Returns:
            Dictionary with input preview data.
        """
        pipeline = self.pipelineConfig
        if stepIndex >= len(pipeline.steps):
            return {"error": f"Step index {stepIndex} out of range"}

        step = pipeline.steps[stepIndex]
        return self._buildStepInputs(step, stepIndex)

    def _executeStepByType(self, step: PipelineStep, stepIndex: int) -> StepResult:
        """Execute a step based on its type.

        Args:
            step: The pipeline step to execute.
            stepIndex: Index of the step.

        Returns:
            Result of the step execution.
        """
        startTime = time.time()
        inputs = self._buildStepInputs(step, stepIndex)

        result = StepResult(
            stepName=step.step,
            status=StepStatus.RUNNING,
            inputs=inputs,
        )

        try:
            if self._dryRunMode:
                outputs = self._dryRunStep(step, inputs)
            else:
                outputs = self._executeRealStep(step, inputs)

            result.outputs = outputs
            result.status = StepStatus.COMPLETED

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"Step '{step.step}' failed: {e}")

        result.duration = time.time() - startTime
        return result

    def _buildStepInputs(self, step: PipelineStep, stepIndex: int) -> dict[str, Any]:
        """Build input data for a step.

        Args:
            step: The pipeline step.
            stepIndex: Index of the step.

        Returns:
            Input dictionary for the step.
        """
        simulation = self._engine.simulation
        inputs: dict[str, Any] = {
            "stepIndex": stepIndex,
            "stepConfig": step.config,
            "turnNumber": self._engine.currentTurn,
        }

        if step.step == "turn_start":
            inputs["previousTurnResult"] = (
                self._engine.state.lastTurnResult.toDict()
                if self._engine.state.lastTurnResult
                else None
            )

        elif step.step == "gather_events":
            inputs["scheduledEvents"] = len(self._engine._scheduledEvents)
            inputs["turnNumber"] = self._engine.currentTurn + 1

        elif step.step == "orchestrator_decide":
            inputs["events"] = [e.toDict() for e in self._currentTurnEvents]
            inputs["worldState"] = simulation.getWorldState()
            inputs["availableAgents"] = [
                {"name": a.name, "role": a.role}
                for a in simulation.getCpuAgents()
                if a.name != self.pipelineConfig.orchestratorName
            ]
            inputs["orchestratorName"] = self.pipelineConfig.orchestratorName

        elif step.step == "execute_agents":
            # Get from previous orchestrator decision if available
            if self._engine.lastOrchestratorDecision:
                inputs["agentsToWake"] = (
                    self._engine.lastOrchestratorDecision.agentsToWake
                )
                inputs["instructions"] = (
                    self._engine.lastOrchestratorDecision.instructions
                )
            else:
                inputs["agentsToWake"] = []
                inputs["instructions"] = {}

        elif step.step == "player_turn":
            inputs["playerAgent"] = simulation.getPlayerAgentName()
            inputs["skipPlayerTurn"] = (
                self._engine.lastOrchestratorDecision.skipPlayerTurn
                if self._engine.lastOrchestratorDecision
                else False
            )

        return inputs

    def _executeRealStep(self, step: PipelineStep, inputs: dict[str, Any]) -> dict:
        """Execute a step with real LLM calls.

        Args:
            step: The pipeline step.
            inputs: Input data for the step.

        Returns:
            Output dictionary from the step.
        """
        outputs: dict[str, Any] = {}

        if step.step == "turn_start":
            # Emit turn_start event
            event = Event(
                name="turn_start", data={"turn": self._engine.currentTurn + 1}
            )
            self._currentTurnEvents.append(event)
            outputs["event"] = event.toDict()

        elif step.step == "gather_events":
            # Gather player events from simulation's event history
            simulation = self._engine.simulation
            recentEvents = simulation.getEventHistory(limit=10)
            worldState = simulation.getWorldState()

            # Track last processed event timestamp to avoid reprocessing
            lastProcessedTime = worldState.get("_lastEventProcessedTime", "")

            # Add player-related events to current turn events
            playerEvents = []
            newestEventTime = lastProcessedTime
            for eventDict in recentEvents:
                eventName = eventDict.get("name", "")
                eventTime = eventDict.get("timestamp", "")

                # Skip already processed events
                if eventTime and eventTime <= lastProcessedTime:
                    continue

                # Include player actions and messages
                if eventName.startswith("player_"):
                    # Convert dict back to Event object
                    event = Event(
                        name=eventName,
                        data=eventDict.get("data", {}),
                        source=eventDict.get("source", "player"),
                    )
                    self._currentTurnEvents.append(event)
                    playerEvents.append(eventDict)

                    # Track newest event time
                    if eventTime > newestEventTime:
                        newestEventTime = eventTime

            # Update last processed time in world state
            if newestEventTime > lastProcessedTime:
                worldState["_lastEventProcessedTime"] = newestEventTime
                simulation.setWorldState(worldState)

            outputs["eventsGathered"] = len(self._currentTurnEvents)
            outputs["playerEvents"] = playerEvents

        elif step.step == "orchestrator_decide":
            # This triggers the orchestrator LLM call
            simulation = self._engine.simulation
            availableAgents = [
                a
                for a in simulation.getCpuAgents()
                if a.name != self.pipelineConfig.orchestratorName
            ]

            decision = self._engine._askOrchestrator(
                events=self._currentTurnEvents,
                worldState=simulation.getWorldState(),
                availableAgents=availableAgents,
            )
            self._engine._lastOrchestratorDecision = decision

            outputs["decision"] = decision.toDict()
            outputs["agentsSelected"] = decision.agentsToWake

        elif step.step == "execute_agents":
            # Execute selected agents
            actions = []
            if self._engine.lastOrchestratorDecision:
                for agentName in self._engine.lastOrchestratorDecision.agentsToWake:
                    instruction = (
                        self._engine.lastOrchestratorDecision.instructions.get(
                            agentName
                        )
                    )
                    action = self._engine._generateCpuActionWithInstruction(
                        agentName, instruction
                    )
                    if action:
                        actions.append(action.toDict())

            outputs["actions"] = actions
            outputs["agentsExecuted"] = len(actions)

        elif step.step == "player_turn":
            outputs["playerPending"] = True
            outputs["playerAgent"] = inputs.get("playerAgent")

        return outputs

    def _dryRunStep(self, step: PipelineStep, inputs: dict[str, Any]) -> dict:
        """Simulate a step without real execution.

        Args:
            step: The pipeline step.
            inputs: Input data for the step.

        Returns:
            Simulated output dictionary.
        """
        outputs: dict[str, Any] = {"dryRun": True}

        if step.step == "turn_start":
            outputs["event"] = {
                "name": "turn_start",
                "data": {"turn": self._engine.currentTurn + 1},
            }

        elif step.step == "gather_events":
            outputs["eventsGathered"] = 0
            outputs["wouldProcess"] = inputs.get("scheduledEvents", 0)

        elif step.step == "orchestrator_decide":
            outputs["wouldCall"] = inputs.get("orchestratorName")
            outputs["availableAgents"] = [
                a["name"] for a in inputs.get("availableAgents", [])
            ]
            outputs["note"] = "Would make LLM call to orchestrator"

        elif step.step == "execute_agents":
            outputs["wouldExecute"] = inputs.get("agentsToWake", [])
            outputs["note"] = "Would make LLM calls for each selected agent"

        elif step.step == "player_turn":
            outputs["playerPending"] = not inputs.get("skipPlayerTurn", False)

        return outputs
