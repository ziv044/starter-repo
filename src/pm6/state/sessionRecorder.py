"""Session recording for interaction history.

Records all simulation interactions for replay, analysis, and debugging.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("pm6.state")


@dataclass
class InteractionRecord:
    """Record of a single interaction.

    Attributes:
        timestamp: When the interaction occurred.
        agentName: Name of the agent.
        userInput: User's input message.
        response: Agent's response.
        situationType: Type of situation.
        fromCache: Whether response was cached.
        model: Model used (if not cached).
        usage: Token usage (if not cached).
        worldState: World state at time of interaction.
        metadata: Additional metadata.
    """

    timestamp: str
    agentName: str
    userInput: str
    response: str
    situationType: str = "general"
    fromCache: bool = False
    model: str | None = None
    usage: dict[str, int] | None = None
    worldState: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "InteractionRecord":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SessionMetadata:
    """Metadata for a recorded session.

    Attributes:
        sessionId: Unique session identifier.
        simulationName: Name of the simulation.
        startTime: When the session started.
        endTime: When the session ended (None if ongoing).
        interactionCount: Number of interactions.
        agents: List of agents involved.
        totalCost: Total cost of the session.
    """

    sessionId: str
    simulationName: str
    startTime: str
    endTime: str | None = None
    interactionCount: int = 0
    agents: list[str] = field(default_factory=list)
    totalCost: float = 0.0


class SessionRecorder:
    """Records simulation sessions for replay and analysis.

    Args:
        basePath: Base directory for session storage.
        simulationName: Name of the simulation.
    """

    def __init__(self, basePath: Path, simulationName: str):
        self.basePath = basePath
        self.simulationName = simulationName
        self._sessionsPath = basePath / simulationName / "sessions"
        self._sessionsPath.mkdir(parents=True, exist_ok=True)

        self._currentSession: str | None = None
        self._interactions: list[InteractionRecord] = []
        self._metadata: SessionMetadata | None = None

    def startSession(self, sessionId: str | None = None) -> str:
        """Start recording a new session.

        Args:
            sessionId: Optional custom session ID.

        Returns:
            The session ID.
        """
        if sessionId is None:
            sessionId = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._currentSession = sessionId
        self._interactions = []
        self._metadata = SessionMetadata(
            sessionId=sessionId,
            simulationName=self.simulationName,
            startTime=datetime.now().isoformat(),
        )

        logger.info(f"Started session: {sessionId}")
        return sessionId

    def recordInteraction(
        self,
        agentName: str,
        userInput: str,
        response: str,
        situationType: str = "general",
        fromCache: bool = False,
        model: str | None = None,
        usage: dict[str, int] | None = None,
        worldState: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an interaction.

        Args:
            agentName: Name of the agent.
            userInput: User's input.
            response: Agent's response.
            situationType: Type of situation.
            fromCache: Whether response was cached.
            model: Model used.
            usage: Token usage.
            worldState: Current world state.
            metadata: Additional metadata.
        """
        if self._currentSession is None:
            self.startSession()

        record = InteractionRecord(
            timestamp=datetime.now().isoformat(),
            agentName=agentName,
            userInput=userInput,
            response=response,
            situationType=situationType,
            fromCache=fromCache,
            model=model,
            usage=usage,
            worldState=worldState or {},
            metadata=metadata or {},
        )

        self._interactions.append(record)

        # Update metadata
        if self._metadata:
            self._metadata.interactionCount = len(self._interactions)
            if agentName not in self._metadata.agents:
                self._metadata.agents.append(agentName)

        logger.debug(f"Recorded interaction with {agentName}")

    def endSession(self, totalCost: float = 0.0) -> None:
        """End the current session and save to disk.

        Args:
            totalCost: Total cost of the session.
        """
        if self._currentSession is None:
            return

        if self._metadata:
            self._metadata.endTime = datetime.now().isoformat()
            self._metadata.totalCost = totalCost

        self._saveSession()
        logger.info(f"Ended session: {self._currentSession}")

        self._currentSession = None
        self._interactions = []
        self._metadata = None

    def getInteractions(self) -> list[InteractionRecord]:
        """Get all interactions from the current session.

        Returns:
            List of interaction records.
        """
        return list(self._interactions)

    def _saveSession(self) -> None:
        """Save current session to disk."""
        if self._currentSession is None or self._metadata is None:
            return

        sessionPath = self._sessionsPath / f"{self._currentSession}.json"
        data = {
            "metadata": asdict(self._metadata),
            "interactions": [i.toDict() for i in self._interactions],
        }

        with open(sessionPath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved session: {sessionPath}")

    def loadSession(self, sessionId: str) -> dict[str, Any]:
        """Load a recorded session.

        Args:
            sessionId: Session ID to load.

        Returns:
            Session data with metadata and interactions.
        """
        sessionPath = self._sessionsPath / f"{sessionId}.json"

        if not sessionPath.exists():
            raise FileNotFoundError(f"Session not found: {sessionId}")

        with open(sessionPath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def listSessions(self) -> list[dict[str, Any]]:
        """List all recorded sessions.

        Returns:
            List of session metadata dicts.
        """
        sessions = []
        for path in self._sessionsPath.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(data.get("metadata", {"sessionId": path.stem}))
            except (json.JSONDecodeError, KeyError):
                sessions.append({"sessionId": path.stem, "error": "Invalid format"})

        return sorted(sessions, key=lambda x: x.get("startTime", ""), reverse=True)

    def deleteSession(self, sessionId: str) -> None:
        """Delete a recorded session.

        Args:
            sessionId: Session ID to delete.
        """
        sessionPath = self._sessionsPath / f"{sessionId}.json"
        if sessionPath.exists():
            sessionPath.unlink()
            logger.info(f"Deleted session: {sessionId}")

    def exportSession(self, sessionId: str, format: str = "json") -> str:
        """Export a session in the specified format.

        Args:
            sessionId: Session ID to export.
            format: Export format ('json' or 'jsonl').

        Returns:
            Exported data as string.
        """
        data = self.loadSession(sessionId)

        if format == "jsonl":
            lines = []
            for interaction in data.get("interactions", []):
                lines.append(json.dumps(interaction, ensure_ascii=False))
            return "\n".join(lines)

        return json.dumps(data, indent=2, ensure_ascii=False)

    def getSessionStats(self, sessionId: str) -> dict[str, Any]:
        """Get statistics for a session.

        Args:
            sessionId: Session ID.

        Returns:
            Session statistics.
        """
        data = self.loadSession(sessionId)
        interactions = data.get("interactions", [])
        metadata = data.get("metadata", {})

        cacheHits = sum(1 for i in interactions if i.get("fromCache", False))
        totalTokens = sum(
            (i.get("usage", {}).get("inputTokens", 0) or 0)
            + (i.get("usage", {}).get("outputTokens", 0) or 0)
            for i in interactions
        )

        return {
            "sessionId": sessionId,
            "interactionCount": len(interactions),
            "agents": metadata.get("agents", []),
            "cacheHits": cacheHits,
            "cacheMisses": len(interactions) - cacheHits,
            "cacheHitRate": cacheHits / len(interactions) if interactions else 0,
            "totalTokens": totalTokens,
            "totalCost": metadata.get("totalCost", 0),
            "duration": self._calculateDuration(
                metadata.get("startTime"), metadata.get("endTime")
            ),
        }

    def _calculateDuration(
        self, startTime: str | None, endTime: str | None
    ) -> float | None:
        """Calculate session duration in seconds."""
        if not startTime or not endTime:
            return None

        try:
            start = datetime.fromisoformat(startTime)
            end = datetime.fromisoformat(endTime)
            return (end - start).total_seconds()
        except ValueError:
            return None

    @property
    def isRecording(self) -> bool:
        """Check if a session is currently being recorded."""
        return self._currentSession is not None

    @property
    def currentSessionId(self) -> str | None:
        """Get the current session ID."""
        return self._currentSession
