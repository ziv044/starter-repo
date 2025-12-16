"""Memory policy definitions for agents.

Memory policies control how agents retain and forget information
across interactions to manage context size and relevance.
"""

from enum import Enum
from typing import Any


class MemoryPolicy(str, Enum):
    """Memory retention policy for agents.

    Attributes:
        FULL: Retain complete interaction history.
        SUMMARY: Compact history after N turns into summary.
        SELECTIVE: Remember only specific categories of information.
        NONE: Stateless agent - no memory between interactions.
    """

    FULL = "full"
    SUMMARY = "summary"
    SELECTIVE = "selective"
    NONE = "none"


class MemoryManager:
    """Manages agent memory according to policy.

    Args:
        policy: The memory policy to apply.
        maxTurns: Maximum turns before compaction (for SUMMARY policy).
        categories: Categories to retain (for SELECTIVE policy).
    """

    def __init__(
        self,
        policy: MemoryPolicy = MemoryPolicy.SUMMARY,
        maxTurns: int = 10,
        categories: list[str] | None = None,
    ):
        self.policy = policy
        self.maxTurns = maxTurns
        self.categories = categories or []
        self._history: list[dict[str, Any]] = []

    def addInteraction(self, interaction: dict[str, Any]) -> None:
        """Add an interaction to memory.

        Args:
            interaction: The interaction to remember.
        """
        if self.policy == MemoryPolicy.NONE:
            return

        self._history.append(interaction)

    def getHistory(self) -> list[dict[str, Any]]:
        """Get the current interaction history.

        Returns:
            List of remembered interactions.
        """
        if self.policy == MemoryPolicy.NONE:
            return []

        return self._history.copy()

    def needsCompaction(self) -> bool:
        """Check if memory needs compaction.

        Returns:
            True if compaction should be triggered.
        """
        if self.policy != MemoryPolicy.SUMMARY:
            return False

        return len(self._history) >= self.maxTurns

    def clear(self) -> None:
        """Clear all memory."""
        self._history.clear()

    def setCompactedHistory(self, summary: str) -> None:
        """Replace history with a compacted summary.

        Args:
            summary: The compacted summary to store.
        """
        self._history = [{"type": "summary", "content": summary}]
