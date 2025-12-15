"""LLM Replay Provider for deterministic testing."""

import json
from pathlib import Path
from typing import Any

from .config import get_settings
from .exceptions import ReplayNotFoundError, SessionNotFoundError


class LLMReplayProvider:
    """Provider for replaying logged Claude API responses.

    Loads a JSONL session file and provides responses sequentially
    by agent name for deterministic test execution.

    Attributes:
        session_path: Path to the JSONL session file.
    """

    def __init__(self, session_path: str | Path) -> None:
        """Initialize the replay provider.

        Args:
            session_path: Path to the JSONL session file to replay.

        Raises:
            SessionNotFoundError: If the session file doesn't exist.
        """
        self.session_path = Path(session_path)
        if not self.session_path.exists():
            raise SessionNotFoundError(str(self.session_path))

        self._entries: list[dict[str, Any]] = []
        self._agent_indices: dict[str, int] = {}
        self._load_session()

    def _load_session(self) -> None:
        """Load all entries from the session file."""
        with open(self.session_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self._entries.append(json.loads(line))

    def get_response(self, agent_name: str) -> dict[str, Any]:
        """Get the next response for an agent.

        Args:
            agent_name: Name of the agent requesting a response.

        Returns:
            The logged response dictionary.

        Raises:
            ReplayNotFoundError: If no more responses for this agent.
        """
        settings = get_settings()

        # Get current call index for this agent (1-based)
        current_index = self._agent_indices.get(agent_name, 0) + 1

        # Find the matching entry
        for entry in self._entries:
            if (
                entry.get("agent_name") == agent_name
                and entry.get("call_index") == current_index
            ):
                self._agent_indices[agent_name] = current_index
                return entry.get("response", {})

        # Not found
        if settings.strict_replay:
            raise ReplayNotFoundError(agent_name, current_index)

        # Non-strict mode returns empty dict (caller should fall back to live)
        return {}

    def has_response(self, agent_name: str) -> bool:
        """Check if there's a next response for an agent.

        Args:
            agent_name: Name of the agent to check.

        Returns:
            True if there's a response available.
        """
        next_index = self._agent_indices.get(agent_name, 0) + 1

        for entry in self._entries:
            if (
                entry.get("agent_name") == agent_name
                and entry.get("call_index") == next_index
            ):
                return True
        return False

    def reset(self, agent_name: str | None = None) -> None:
        """Reset replay indices.

        Args:
            agent_name: If provided, reset only this agent.
                       If None, reset all agents.
        """
        if agent_name is not None:
            self._agent_indices[agent_name] = 0
        else:
            self._agent_indices.clear()

    def get_agent_call_count(self, agent_name: str) -> int:
        """Get total number of logged calls for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Number of logged calls for the agent.
        """
        return sum(
            1 for entry in self._entries if entry.get("agent_name") == agent_name
        )

    @property
    def total_entries(self) -> int:
        """Total number of entries in the session."""
        return len(self._entries)

    @property
    def agent_names(self) -> list[str]:
        """List of unique agent names in the session."""
        return list(set(entry.get("agent_name", "") for entry in self._entries))
