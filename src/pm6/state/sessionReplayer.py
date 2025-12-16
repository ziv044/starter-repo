"""Session replay functionality.

Enables replaying recorded sessions, branching from any point,
and verifying behavior consistency (FR42).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

logger = logging.getLogger("pm6.state")


@dataclass
class ReplayInteraction:
    """A single interaction from a replay.

    Attributes:
        index: Position in the session.
        agentName: Name of the agent.
        userInput: User's input.
        response: Agent's response.
        situationType: Type of situation.
        fromCache: Whether response was cached.
        worldState: World state at time of interaction.
        metadata: Additional metadata.
    """

    index: int
    agentName: str
    userInput: str
    response: str
    situationType: str = "general"
    fromCache: bool = False
    worldState: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class SessionReplayer:
    """Replays recorded sessions.

    Args:
        basePath: Base directory for session storage.
        simulationName: Name of the simulation.
    """

    def __init__(self, basePath: Path, simulationName: str):
        self.basePath = basePath
        self.simulationName = simulationName
        self._sessionsPath = basePath / simulationName / "sessions"

        self._currentSession: dict[str, Any] | None = None
        self._currentIndex: int = 0
        self._interactions: list[dict[str, Any]] = []

    def loadSession(self, sessionId: str) -> dict[str, Any]:
        """Load a session for replay.

        Args:
            sessionId: Session ID to load.

        Returns:
            Session metadata.
        """
        sessionPath = self._sessionsPath / f"{sessionId}.json"

        if not sessionPath.exists():
            raise FileNotFoundError(f"Session not found: {sessionId}")

        with open(sessionPath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._currentSession = data
        self._interactions = data.get("interactions", [])
        self._currentIndex = 0

        logger.info(f"Loaded session for replay: {sessionId}")
        return data.get("metadata", {})

    def reset(self) -> None:
        """Reset replay to the beginning."""
        self._currentIndex = 0

    def seekTo(self, index: int) -> None:
        """Seek to a specific interaction index.

        Args:
            index: Index to seek to.
        """
        if index < 0 or index >= len(self._interactions):
            raise IndexError(f"Index {index} out of range (0-{len(self._interactions)-1})")
        self._currentIndex = index

    def next(self) -> ReplayInteraction | None:
        """Get the next interaction.

        Returns:
            Next interaction or None if at end.
        """
        if self._currentIndex >= len(self._interactions):
            return None

        interaction = self._interactions[self._currentIndex]
        result = ReplayInteraction(
            index=self._currentIndex,
            agentName=interaction.get("agentName", ""),
            userInput=interaction.get("userInput", ""),
            response=interaction.get("response", ""),
            situationType=interaction.get("situationType", "general"),
            fromCache=interaction.get("fromCache", False),
            worldState=interaction.get("worldState"),
            metadata=interaction.get("metadata"),
        )

        self._currentIndex += 1
        return result

    def previous(self) -> ReplayInteraction | None:
        """Get the previous interaction.

        Returns:
            Previous interaction or None if at start.
        """
        if self._currentIndex <= 0:
            return None

        self._currentIndex -= 1
        return self.current()

    def current(self) -> ReplayInteraction | None:
        """Get the current interaction without advancing.

        Returns:
            Current interaction or None if invalid.
        """
        if self._currentIndex < 0 or self._currentIndex >= len(self._interactions):
            return None

        interaction = self._interactions[self._currentIndex]
        return ReplayInteraction(
            index=self._currentIndex,
            agentName=interaction.get("agentName", ""),
            userInput=interaction.get("userInput", ""),
            response=interaction.get("response", ""),
            situationType=interaction.get("situationType", "general"),
            fromCache=interaction.get("fromCache", False),
            worldState=interaction.get("worldState"),
            metadata=interaction.get("metadata"),
        )

    def iterate(self) -> Iterator[ReplayInteraction]:
        """Iterate through all interactions.

        Yields:
            Each interaction in order.
        """
        self.reset()
        while True:
            interaction = self.next()
            if interaction is None:
                break
            yield interaction

    def getInteractionAt(self, index: int) -> ReplayInteraction | None:
        """Get interaction at a specific index.

        Args:
            index: Index to retrieve.

        Returns:
            Interaction at index or None if invalid.
        """
        if index < 0 or index >= len(self._interactions):
            return None

        interaction = self._interactions[index]
        return ReplayInteraction(
            index=index,
            agentName=interaction.get("agentName", ""),
            userInput=interaction.get("userInput", ""),
            response=interaction.get("response", ""),
            situationType=interaction.get("situationType", "general"),
            fromCache=interaction.get("fromCache", False),
            worldState=interaction.get("worldState"),
            metadata=interaction.get("metadata"),
        )

    def getWorldStateAt(self, index: int) -> dict[str, Any]:
        """Get the world state at a specific point.

        Args:
            index: Interaction index.

        Returns:
            World state at that point.
        """
        interaction = self.getInteractionAt(index)
        if interaction is None or interaction.worldState is None:
            return {}
        return interaction.worldState.copy()

    def branchFrom(self, index: int) -> dict[str, Any]:
        """Get data needed to branch from a specific point.

        Args:
            index: Interaction index to branch from.

        Returns:
            Dict with worldState and interactions up to that point.
        """
        if index < 0 or index >= len(self._interactions):
            raise IndexError(f"Index {index} out of range")

        # Get world state at branch point
        worldState = self.getWorldStateAt(index)

        # Get interactions up to branch point
        interactions = self._interactions[: index + 1]

        return {
            "branchPoint": index,
            "worldState": worldState,
            "interactions": interactions,
            "metadata": self._currentSession.get("metadata", {}) if self._currentSession else {},
        }

    def findInteractions(
        self,
        agentName: str | None = None,
        situationType: str | None = None,
    ) -> list[ReplayInteraction]:
        """Find interactions matching criteria.

        Args:
            agentName: Filter by agent name.
            situationType: Filter by situation type.

        Returns:
            List of matching interactions.
        """
        results = []
        for i, interaction in enumerate(self._interactions):
            if agentName and interaction.get("agentName") != agentName:
                continue
            if situationType and interaction.get("situationType") != situationType:
                continue

            results.append(
                ReplayInteraction(
                    index=i,
                    agentName=interaction.get("agentName", ""),
                    userInput=interaction.get("userInput", ""),
                    response=interaction.get("response", ""),
                    situationType=interaction.get("situationType", "general"),
                    fromCache=interaction.get("fromCache", False),
                    worldState=interaction.get("worldState"),
                    metadata=interaction.get("metadata"),
                )
            )

        return results

    @property
    def position(self) -> int:
        """Current replay position."""
        return self._currentIndex

    @property
    def length(self) -> int:
        """Total number of interactions."""
        return len(self._interactions)

    @property
    def isAtEnd(self) -> bool:
        """Check if at end of session."""
        return self._currentIndex >= len(self._interactions)

    @property
    def isAtStart(self) -> bool:
        """Check if at start of session."""
        return self._currentIndex == 0


@dataclass
class ResponseComparison:
    """Comparison between original and replayed response.

    Attributes:
        index: Interaction index.
        agentName: Name of the agent.
        userInput: The user input.
        originalResponse: Original recorded response.
        replayedResponse: Response from replay.
        match: Whether responses match according to comparator.
        similarity: Similarity score (0-1) if available.
        metadata: Additional comparison metadata.
    """

    index: int
    agentName: str
    userInput: str
    originalResponse: str
    replayedResponse: str
    match: bool
    similarity: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayVerificationResult:
    """Result of replaying a session for behavior verification.

    Attributes:
        sessionId: ID of the verified session.
        totalInteractions: Number of interactions replayed.
        matchingResponses: Number of responses that matched.
        driftedResponses: Number of responses that differed.
        comparisons: Detailed comparison for each interaction.
        passed: Whether verification passed (all matched or within threshold).
        driftThreshold: Allowed drift percentage.
        actualDriftRate: Actual percentage of drifted responses.
    """

    sessionId: str
    totalInteractions: int
    matchingResponses: int
    driftedResponses: int
    comparisons: list[ResponseComparison]
    passed: bool
    driftThreshold: float = 0.0
    actualDriftRate: float = 0.0

    def getDriftedInteractions(self) -> list[ResponseComparison]:
        """Get all interactions where responses differed."""
        return [c for c in self.comparisons if not c.match]

    def getMatchedInteractions(self) -> list[ResponseComparison]:
        """Get all interactions where responses matched."""
        return [c for c in self.comparisons if c.match]

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sessionId": self.sessionId,
            "totalInteractions": self.totalInteractions,
            "matchingResponses": self.matchingResponses,
            "driftedResponses": self.driftedResponses,
            "passed": self.passed,
            "driftThreshold": self.driftThreshold,
            "actualDriftRate": self.actualDriftRate,
            "comparisons": [
                {
                    "index": c.index,
                    "agentName": c.agentName,
                    "match": c.match,
                    "similarity": c.similarity,
                }
                for c in self.comparisons
            ],
        }


def defaultResponseComparator(original: str, replayed: str) -> tuple[bool, float | None]:
    """Default exact-match comparator for responses.

    Args:
        original: Original response.
        replayed: Replayed response.

    Returns:
        Tuple of (match, similarity_score).
    """
    match = original.strip() == replayed.strip()
    return match, 1.0 if match else 0.0


class ReplayVerifier:
    """Verifies session replay behavior consistency.

    Replays sessions and compares responses to detect behavioral drift.

    Args:
        replayer: SessionReplayer instance.
        responseGenerator: Callable that generates a response given agent and input.
    """

    def __init__(
        self,
        replayer: "SessionReplayer",
        responseGenerator: Callable[[str, str, dict[str, Any] | None], str],
    ):
        self._replayer = replayer
        self._responseGenerator = responseGenerator

    def verify(
        self,
        sessionId: str,
        driftThreshold: float = 0.0,
        comparator: Callable[[str, str], tuple[bool, float | None]] | None = None,
        agentFilter: str | list[str] | None = None,
    ) -> ReplayVerificationResult:
        """Verify a session by replaying and comparing responses.

        Args:
            sessionId: Session ID to verify.
            driftThreshold: Allowed percentage of drifted responses (0.0-1.0).
            comparator: Custom function to compare responses.
            agentFilter: Only verify specific agent(s).

        Returns:
            ReplayVerificationResult with detailed comparison.
        """
        if comparator is None:
            comparator = defaultResponseComparator

        if isinstance(agentFilter, str):
            agentFilter = [agentFilter]

        self._replayer.loadSession(sessionId)
        comparisons: list[ResponseComparison] = []
        matchCount = 0

        for interaction in self._replayer.iterate():
            # Skip if agent filtered out
            if agentFilter and interaction.agentName not in agentFilter:
                continue

            # Generate replay response
            try:
                replayedResponse = self._responseGenerator(
                    interaction.agentName,
                    interaction.userInput,
                    interaction.worldState,
                )
            except Exception as e:
                logger.error(f"Failed to generate replay response: {e}")
                replayedResponse = f"[ERROR: {e}]"

            # Compare
            match, similarity = comparator(interaction.response, replayedResponse)

            if match:
                matchCount += 1

            comparison = ResponseComparison(
                index=interaction.index,
                agentName=interaction.agentName,
                userInput=interaction.userInput,
                originalResponse=interaction.response,
                replayedResponse=replayedResponse,
                match=match,
                similarity=similarity,
            )
            comparisons.append(comparison)

        totalCount = len(comparisons)
        driftCount = totalCount - matchCount
        driftRate = driftCount / totalCount if totalCount > 0 else 0.0

        passed = driftRate <= driftThreshold

        result = ReplayVerificationResult(
            sessionId=sessionId,
            totalInteractions=totalCount,
            matchingResponses=matchCount,
            driftedResponses=driftCount,
            comparisons=comparisons,
            passed=passed,
            driftThreshold=driftThreshold,
            actualDriftRate=driftRate,
        )

        logger.info(
            f"Replay verification: {sessionId} - "
            f"{matchCount}/{totalCount} matched, "
            f"drift={driftRate:.1%}, passed={passed}"
        )

        return result
