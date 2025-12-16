"""Folder-based storage for simulation state.

Provides persistent storage for agents, sessions, and world state
using a simple folder/JSON structure for development speed.
"""

import json
import logging
from pathlib import Path
from typing import Any

from pm6.exceptions import StorageError

logger = logging.getLogger("pm6.state")


class Storage:
    """Folder-based storage for simulation data.

    Structure:
        db/{simulationName}/
            agents/          - Agent configurations
            sessions/        - Session history
            state/           - World state snapshots
            responses/       - Cached responses

    Args:
        basePath: Base directory for all storage.
        simulationName: Name of the simulation.
    """

    def __init__(self, basePath: Path, simulationName: str):
        self.basePath = basePath
        self.simulationName = simulationName
        self._simulationPath = basePath / simulationName
        self._ensurePaths()

    def _ensurePaths(self) -> None:
        """Ensure all storage directories exist."""
        for subdir in ["agents", "sessions", "state", "responses"]:
            (self._simulationPath / subdir).mkdir(parents=True, exist_ok=True)

    @property
    def agentsPath(self) -> Path:
        """Path to agents storage."""
        return self._simulationPath / "agents"

    @property
    def sessionsPath(self) -> Path:
        """Path to sessions storage."""
        return self._simulationPath / "sessions"

    @property
    def statePath(self) -> Path:
        """Path to state storage."""
        return self._simulationPath / "state"

    @property
    def responsesPath(self) -> Path:
        """Path to responses cache."""
        return self._simulationPath / "responses"

    def saveJson(self, path: Path, data: dict[str, Any]) -> None:
        """Save data as JSON.

        Args:
            path: File path to save to.
            data: Data to serialize.

        Raises:
            StorageError: If save fails.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.debug(f"Saved: {path}")
        except (OSError, TypeError) as e:
            raise StorageError(f"Failed to save {path}: {e}") from e

    def loadJson(self, path: Path) -> dict[str, Any]:
        """Load data from JSON.

        Args:
            path: File path to load from.

        Returns:
            Loaded data.

        Raises:
            StorageError: If load fails.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise StorageError(f"File not found: {path}")
        except json.JSONDecodeError as e:
            raise StorageError(f"Invalid JSON in {path}: {e}") from e

    def exists(self, path: Path) -> bool:
        """Check if a file exists."""
        return path.exists()

    def delete(self, path: Path) -> None:
        """Delete a file.

        Args:
            path: File to delete.
        """
        if path.exists():
            path.unlink()
            logger.debug(f"Deleted: {path}")

    def listFiles(self, directory: Path, pattern: str = "*.json") -> list[Path]:
        """List files in a directory.

        Args:
            directory: Directory to list.
            pattern: Glob pattern to match.

        Returns:
            List of matching file paths.
        """
        if not directory.exists():
            return []
        return list(directory.glob(pattern))

    # Agent-specific methods

    def saveAgent(self, agentName: str, data: dict[str, Any]) -> None:
        """Save agent configuration."""
        path = self.agentsPath / f"{agentName}.json"
        self.saveJson(path, data)

    def loadAgent(self, agentName: str) -> dict[str, Any]:
        """Load agent configuration."""
        path = self.agentsPath / f"{agentName}.json"
        return self.loadJson(path)

    def listAgents(self) -> list[str]:
        """List all saved agents."""
        files = self.listFiles(self.agentsPath)
        return [f.stem for f in files]

    # State-specific methods

    def saveState(self, stateName: str, data: dict[str, Any]) -> None:
        """Save world state."""
        path = self.statePath / f"{stateName}.json"
        self.saveJson(path, data)

    def loadState(self, stateName: str) -> dict[str, Any]:
        """Load world state."""
        path = self.statePath / f"{stateName}.json"
        return self.loadJson(path)

    def listStates(self) -> list[str]:
        """List all saved states."""
        files = self.listFiles(self.statePath)
        return [f.stem for f in files]

    # Session-specific methods

    def saveSession(self, sessionId: str, data: dict[str, Any]) -> None:
        """Save session data."""
        path = self.sessionsPath / f"{sessionId}.json"
        self.saveJson(path, data)

    def loadSession(self, sessionId: str) -> dict[str, Any]:
        """Load session data."""
        path = self.sessionsPath / f"{sessionId}.json"
        return self.loadJson(path)

    def listSessions(self) -> list[str]:
        """List all saved sessions."""
        files = self.listFiles(self.sessionsPath)
        return [f.stem for f in files]
