"""Checkpoint management for save/load functionality.

Enables saving simulation state at any point and resuming later.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pm6.exceptions import SessionNotFoundError, StorageError

logger = logging.getLogger("pm6.state")


@dataclass
class Checkpoint:
    """A saved checkpoint of simulation state.

    Attributes:
        name: Checkpoint name.
        timestamp: When checkpoint was created.
        simulationName: Name of the simulation.
        worldState: Saved world state.
        agentStates: Per-agent memory/state.
        metadata: Additional checkpoint data.
    """

    name: str
    timestamp: datetime
    simulationName: str
    worldState: dict[str, Any] = field(default_factory=dict)
    agentStates: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "simulationName": self.simulationName,
            "worldState": self.worldState,
            "agentStates": self.agentStates,
            "metadata": self.metadata,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            simulationName=data["simulationName"],
            worldState=data.get("worldState", {}),
            agentStates=data.get("agentStates", {}),
            metadata=data.get("metadata", {}),
        )


class CheckpointManager:
    """Manages checkpoints for a simulation.

    Args:
        basePath: Base path for checkpoint storage.
        simulationName: Name of the simulation.
    """

    def __init__(self, basePath: Path, simulationName: str):
        self.basePath = basePath
        self.simulationName = simulationName
        self._checkpointsPath = basePath / simulationName / "checkpoints"
        self._ensurePath()

    def _ensurePath(self) -> None:
        """Ensure checkpoints directory exists."""
        self._checkpointsPath.mkdir(parents=True, exist_ok=True)

    def _getCheckpointPath(self, name: str) -> Path:
        """Get path for a checkpoint file."""
        return self._checkpointsPath / f"{name}.json"

    def save(
        self,
        name: str,
        worldState: dict[str, Any],
        agentStates: dict[str, dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """Save a checkpoint.

        Args:
            name: Checkpoint name.
            worldState: Current world state.
            agentStates: Per-agent states.
            metadata: Additional metadata.

        Returns:
            The saved checkpoint.

        Raises:
            StorageError: If save fails.
        """
        checkpoint = Checkpoint(
            name=name,
            timestamp=datetime.now(),
            simulationName=self.simulationName,
            worldState=worldState,
            agentStates=agentStates,
            metadata=metadata or {},
        )

        path = self._getCheckpointPath(name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.toDict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved checkpoint: {name}")
        except OSError as e:
            raise StorageError(f"Failed to save checkpoint {name}: {e}") from e

        return checkpoint

    def load(self, name: str) -> Checkpoint:
        """Load a checkpoint.

        Args:
            name: Checkpoint name to load.

        Returns:
            The loaded checkpoint.

        Raises:
            SessionNotFoundError: If checkpoint doesn't exist.
            StorageError: If load fails.
        """
        path = self._getCheckpointPath(name)

        if not path.exists():
            raise SessionNotFoundError(self.simulationName, name)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Loaded checkpoint: {name}")
            return Checkpoint.fromDict(data)
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid checkpoint {name}: {e}") from e

    def exists(self, name: str) -> bool:
        """Check if a checkpoint exists.

        Args:
            name: Checkpoint name.

        Returns:
            True if checkpoint exists.
        """
        return self._getCheckpointPath(name).exists()

    def delete(self, name: str) -> None:
        """Delete a checkpoint.

        Args:
            name: Checkpoint name to delete.
        """
        path = self._getCheckpointPath(name)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted checkpoint: {name}")

    def list(self) -> list[str]:
        """List all checkpoints.

        Returns:
            List of checkpoint names.
        """
        files = self._checkpointsPath.glob("*.json")
        return [f.stem for f in files]

    def getLatest(self) -> Checkpoint | None:
        """Get the most recent checkpoint.

        Returns:
            Most recent checkpoint, or None if none exist.
        """
        checkpoints = self.list()
        if not checkpoints:
            return None

        # Load all and find most recent
        latest: Checkpoint | None = None
        for name in checkpoints:
            try:
                cp = self.load(name)
                if latest is None or cp.timestamp > latest.timestamp:
                    latest = cp
            except (SessionNotFoundError, StorageError):
                continue

        return latest
