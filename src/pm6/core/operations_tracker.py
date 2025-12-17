"""Operations Tracker for managing active time-bound operations.

Tracks operations from authorization through completion/failure.
Updates progress each turn based on game time elapsed.
Triggers completion events and notifies owning agents.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from pm6.core.action_items import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
    ActiveOperation,
    OperationStatus,
)

if TYPE_CHECKING:
    from pm6.core.simulation import Simulation

logger = logging.getLogger("pm6.core.operations_tracker")


@dataclass
class OperationUpdate:
    """Result of an operation progress update."""

    operation_id: str
    operation_name: str
    previous_progress: float
    new_progress: float
    status_changed: bool
    new_status: OperationStatus | None = None
    milestone_reached: str | None = None
    complication_occurred: bool = False
    complication_description: str = ""


@dataclass
class OperationsTrackerConfig:
    """Configuration for OperationsTracker."""

    enable_complications: bool = False
    complication_check_interval_hours: int = 24
    notify_agent_on_milestone: bool = True
    notify_agent_on_completion: bool = True


class OperationsTracker:
    """Manages all active operations in the simulation.

    Responsibilities:
    - Store active operations
    - Update progress based on game time
    - Trigger completion events
    - Handle complications (optional)
    - Provide operation context to agents
    """

    def __init__(
        self,
        simulation: Simulation,
        config: OperationsTrackerConfig | None = None,
    ) -> None:
        """Initialize operations tracker.

        Args:
            simulation: The simulation instance.
            config: Tracker configuration.
        """
        self._simulation = simulation
        self._config = config or OperationsTrackerConfig()
        self._active_operations: dict[str, ActiveOperation] = {}
        self._completed_operations: list[ActiveOperation] = []
        self._on_completion_callbacks: list[Callable[[ActiveOperation], None]] = []
        self._on_complication_callbacks: list[Callable[[ActiveOperation, str], None]] = []

    @property
    def active_count(self) -> int:
        """Get count of active operations."""
        return len(self._active_operations)

    @property
    def active_operations(self) -> list[ActiveOperation]:
        """Get list of active operations."""
        return list(self._active_operations.values())

    @property
    def completed_operations(self) -> list[ActiveOperation]:
        """Get list of completed operations."""
        return self._completed_operations

    def authorize_operation(self, item: ActionItem, current_turn: int) -> ActiveOperation:
        """Authorize an operation from an action item.

        Args:
            item: The OPERATION action item to authorize.
            current_turn: Current turn number.

        Returns:
            The newly created ActiveOperation.

        Raises:
            ValueError: If item is not an operation type.
        """
        if item.type != ActionItemType.OPERATION:
            raise ValueError(f"Cannot authorize non-operation item: {item.type}")

        # Create active operation
        operation = ActiveOperation.fromActionItem(item, current_turn)
        operation.status = OperationStatus.IN_PROGRESS

        # Store it
        self._active_operations[operation.id] = operation

        # Mark the action item as approved
        item.resolve(ActionItemStatus.APPROVED)

        logger.info(
            f"Authorized operation {operation.codename} ({operation.id}), "
            f"duration: {operation.duration_hours}h"
        )

        return operation

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        """Cancel an active operation.

        Args:
            operation_id: ID of operation to cancel.
            reason: Reason for cancellation.

        Returns:
            True if cancelled, False if not found.
        """
        if operation_id not in self._active_operations:
            logger.warning(f"Operation not found: {operation_id}")
            return False

        operation = self._active_operations.pop(operation_id)
        operation.cancel(reason)
        self._completed_operations.append(operation)

        logger.info(f"Cancelled operation {operation.codename}: {reason}")
        return True

    def update_operations(self, hours_passed: int) -> list[OperationUpdate]:
        """Update all active operations with time passed.

        Called each turn to advance operation progress.

        Args:
            hours_passed: Hours of game time that passed.

        Returns:
            List of operation updates (progress changes, completions, etc.)
        """
        updates: list[OperationUpdate] = []

        for op_id, operation in list(self._active_operations.items()):
            if not operation.is_active():
                continue

            previous_progress = operation.progress_percent
            previous_milestone = operation.current_milestone

            # Update progress
            completed = operation.update_progress(hours_passed)

            # Check for milestone reached
            milestone_reached = None
            if operation.current_milestone > previous_milestone:
                milestone = operation.milestones[operation.current_milestone - 1]
                milestone_reached = milestone.get("name", f"Milestone {operation.current_milestone}")

            # Check for complications
            complication_occurred = False
            complication_description = ""
            if self._config.enable_complications and not completed:
                complication_occurred, complication_description = self._check_complication(
                    operation, hours_passed
                )

            # Create update record
            update = OperationUpdate(
                operation_id=op_id,
                operation_name=operation.codename,
                previous_progress=previous_progress,
                new_progress=operation.progress_percent,
                status_changed=completed or complication_occurred,
                new_status=operation.status if completed else None,
                milestone_reached=milestone_reached,
                complication_occurred=complication_occurred,
                complication_description=complication_description,
            )
            updates.append(update)

            # Handle completion
            if completed:
                self._handle_completion(operation)

            # Handle complication
            if complication_occurred:
                self._handle_complication(operation, complication_description)

        return updates

    def _check_complication(
        self, operation: ActiveOperation, hours_passed: int
    ) -> tuple[bool, str]:
        """Check if a complication occurs this update.

        Args:
            operation: The operation to check.
            hours_passed: Hours passed this update.

        Returns:
            Tuple of (occurred, description).
        """
        if operation.has_complication:
            return False, ""  # Already has complication

        # Scale probability by hours passed
        check_probability = (
            operation.complication_chance
            * hours_passed
            / self._config.complication_check_interval_hours
        )

        if random.random() < check_probability:
            # Complication occurred!
            operation.has_complication = True
            description = self._generate_complication_description(operation)
            return True, description

        return False, ""

    def _generate_complication_description(self, operation: ActiveOperation) -> str:
        """Generate a contextual complication description."""
        complications = {
            "cyber": [
                "Security protocols detected intrusion attempt",
                "Target network went offline unexpectedly",
                "Countermeasures activated, operation exposed",
            ],
            "kinetic": [
                "Unexpected enemy reinforcements arrived",
                "Weather conditions deteriorating",
                "Target location changed",
            ],
            "humint": [
                "Asset communication compromised",
                "Cover identity under suspicion",
                "Handler lost contact with asset",
            ],
            "sigint": [
                "Target switched to encrypted channel",
                "Equipment malfunction detected",
                "Signal interference from unknown source",
            ],
            "recon": [
                "Team detected by patrol",
                "Observation post compromised",
                "Extraction route blocked",
            ],
            "rescue": [
                "Hostage location changed",
                "Additional guards detected",
                "Intel indicates trap possibility",
            ],
            "diplomatic": [
                "Counterpart recalled for consultations",
                "Leaked information complicates talks",
                "Third party interference detected",
            ],
        }

        category_complications = complications.get(operation.category.value, [])
        if category_complications:
            return random.choice(category_complications)
        return "Unexpected complication encountered"

    def _handle_completion(self, operation: ActiveOperation) -> None:
        """Handle operation completion.

        Args:
            operation: The completed operation.
        """
        # Move to completed list
        if operation.id in self._active_operations:
            del self._active_operations[operation.id]
        self._completed_operations.append(operation)

        logger.info(f"Operation completed: {operation.codename}")

        # Fire callbacks
        for callback in self._on_completion_callbacks:
            try:
                callback(operation)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")

    def _handle_complication(self, operation: ActiveOperation, description: str) -> None:
        """Handle operation complication.

        Args:
            operation: The operation with complication.
            description: Description of the complication.
        """
        logger.warning(f"Complication in {operation.codename}: {description}")

        # Fire callbacks
        for callback in self._on_complication_callbacks:
            try:
                callback(operation, description)
            except Exception as e:
                logger.error(f"Error in complication callback: {e}")

    def get_operation(self, operation_id: str) -> ActiveOperation | None:
        """Get an operation by ID.

        Args:
            operation_id: The operation ID.

        Returns:
            The operation or None if not found.
        """
        return self._active_operations.get(operation_id)

    def get_operations_for_agent(self, agent_name: str) -> list[ActiveOperation]:
        """Get all operations owned by an agent.

        Args:
            agent_name: The agent name.

        Returns:
            List of operations owned by the agent.
        """
        return [
            op for op in self._active_operations.values()
            if op.owner_agent == agent_name
        ]

    def get_agent_operation_context(self, agent_name: str) -> str:
        """Get operation context string for an agent's prompt.

        Args:
            agent_name: The agent name.

        Returns:
            Formatted string describing agent's active operations.
        """
        operations = self.get_operations_for_agent(agent_name)
        if not operations:
            return ""

        lines = ["ACTIVE OPERATIONS UNDER YOUR COMMAND:"]
        for op in operations:
            status_emoji = "🔄" if op.is_active() else "✅" if op.status == OperationStatus.COMPLETED else "❌"
            lines.append(
                f"- {status_emoji} {op.codename}: {op.progress_percent:.0f}% complete "
                f"({op.hours_elapsed}h/{op.duration_hours}h)"
            )
            if op.has_complication:
                lines.append(f"  ⚠️ COMPLICATION: Requires attention")

        return "\n".join(lines)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all operations for UI display.

        Returns:
            Dictionary with operation summary.
        """
        active = [op.toDict() for op in self._active_operations.values()]
        completed = [op.toDict() for op in self._completed_operations[-10:]]  # Last 10

        return {
            "active_count": len(self._active_operations),
            "completed_count": len(self._completed_operations),
            "active_operations": active,
            "recent_completed": completed,
        }

    def on_completion(self, callback: Callable[[ActiveOperation], None]) -> None:
        """Register a callback for operation completion.

        Args:
            callback: Function to call when operation completes.
        """
        self._on_completion_callbacks.append(callback)

    def on_complication(
        self, callback: Callable[[ActiveOperation, str], None]
    ) -> None:
        """Register a callback for operation complication.

        Args:
            callback: Function to call when complication occurs.
        """
        self._on_complication_callbacks.append(callback)

    def reset(self) -> None:
        """Reset all operations."""
        self._active_operations.clear()
        self._completed_operations.clear()

    def toDict(self) -> dict[str, Any]:
        """Convert tracker state to dictionary."""
        return {
            "active_operations": {
                op_id: op.toDict() for op_id, op in self._active_operations.items()
            },
            "completed_operations": [op.toDict() for op in self._completed_operations],
            "config": {
                "enable_complications": self._config.enable_complications,
                "complication_check_interval_hours": self._config.complication_check_interval_hours,
            },
        }

    def fromDict(self, data: dict[str, Any]) -> None:
        """Restore tracker state from dictionary."""
        self._active_operations.clear()
        self._completed_operations.clear()

        for op_id, op_data in data.get("active_operations", {}).items():
            self._active_operations[op_id] = ActiveOperation.fromDict(op_data)

        for op_data in data.get("completed_operations", []):
            self._completed_operations.append(ActiveOperation.fromDict(op_data))
