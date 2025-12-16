"""Interaction tracing for debugging.

Provides detailed tracing of simulation interactions for debugging.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("pm6.logging")


class TraceEventType(str, Enum):
    """Types of trace events."""

    INTERACTION_START = "interaction_start"
    INTERACTION_END = "interaction_end"
    CACHE_LOOKUP = "cache_lookup"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    STATE_CHANGE = "state_change"
    RULE_CHECK = "rule_check"
    RULE_VIOLATION = "rule_violation"
    CHECKPOINT_SAVE = "checkpoint_save"
    CHECKPOINT_LOAD = "checkpoint_load"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class TraceEvent:
    """A single trace event.

    Attributes:
        eventType: Type of event.
        timestamp: When the event occurred.
        data: Event-specific data.
        duration: Duration in milliseconds (for timed events).
        agentName: Associated agent name.
        correlationId: ID to correlate related events.
    """

    eventType: TraceEventType | str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: dict[str, Any] = field(default_factory=dict)
    duration: float | None = None
    agentName: str | None = None
    correlationId: str | None = None

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        if isinstance(self.eventType, TraceEventType):
            result["eventType"] = self.eventType.value
        return result


class InteractionTracer:
    """Traces simulation interactions for debugging.

    Records detailed events during simulation execution.

    Args:
        enabled: Whether tracing is enabled.
        outputPath: Optional path to write trace files.
        maxEvents: Maximum events to keep in memory.
    """

    def __init__(
        self,
        enabled: bool = True,
        outputPath: Path | None = None,
        maxEvents: int = 10000,
    ):
        self._enabled = enabled
        self._outputPath = outputPath
        self._maxEvents = maxEvents
        self._events: list[TraceEvent] = []
        self._timers: dict[str, float] = {}
        self._correlationCounter = 0

    def enable(self) -> None:
        """Enable tracing."""
        self._enabled = True

    def disable(self) -> None:
        """Disable tracing."""
        self._enabled = False

    @property
    def isEnabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled

    def newCorrelationId(self) -> str:
        """Generate a new correlation ID for related events."""
        self._correlationCounter += 1
        return f"trace_{self._correlationCounter}"

    def record(
        self,
        eventType: TraceEventType | str,
        data: dict[str, Any] | None = None,
        agentName: str | None = None,
        correlationId: str | None = None,
    ) -> TraceEvent:
        """Record a trace event.

        Args:
            eventType: Type of event.
            data: Event-specific data.
            agentName: Associated agent name.
            correlationId: ID to correlate related events.

        Returns:
            The recorded event.
        """
        if not self._enabled:
            return TraceEvent(eventType=eventType)

        event = TraceEvent(
            eventType=eventType,
            data=data or {},
            agentName=agentName,
            correlationId=correlationId,
        )

        self._events.append(event)

        # Trim if over limit
        if len(self._events) > self._maxEvents:
            self._events = self._events[-self._maxEvents:]

        logger.debug(f"Trace: {eventType} - {data}")
        return event

    def startTimer(self, name: str) -> str:
        """Start a timer for measuring duration.

        Args:
            name: Timer name.

        Returns:
            Timer ID for stopping.
        """
        timerId = f"{name}_{time.time_ns()}"
        self._timers[timerId] = time.perf_counter()
        return timerId

    def stopTimer(self, timerId: str) -> float:
        """Stop a timer and return duration.

        Args:
            timerId: Timer ID from startTimer.

        Returns:
            Duration in milliseconds.
        """
        if timerId not in self._timers:
            return 0.0

        startTime = self._timers.pop(timerId)
        duration = (time.perf_counter() - startTime) * 1000  # Convert to ms
        return duration

    def recordTimed(
        self,
        eventType: TraceEventType | str,
        timerId: str,
        data: dict[str, Any] | None = None,
        agentName: str | None = None,
        correlationId: str | None = None,
    ) -> TraceEvent:
        """Record an event with timing from a timer.

        Args:
            eventType: Type of event.
            timerId: Timer ID to get duration from.
            data: Event-specific data.
            agentName: Associated agent name.
            correlationId: ID to correlate related events.

        Returns:
            The recorded event with duration.
        """
        duration = self.stopTimer(timerId)

        if not self._enabled:
            return TraceEvent(eventType=eventType, duration=duration)

        event = TraceEvent(
            eventType=eventType,
            data=data or {},
            duration=duration,
            agentName=agentName,
            correlationId=correlationId,
        )

        self._events.append(event)

        if len(self._events) > self._maxEvents:
            self._events = self._events[-self._maxEvents:]

        logger.debug(f"Trace: {eventType} ({duration:.2f}ms) - {data}")
        return event

    def getEvents(
        self,
        eventType: TraceEventType | str | None = None,
        agentName: str | None = None,
        correlationId: str | None = None,
        limit: int | None = None,
    ) -> list[TraceEvent]:
        """Get filtered events.

        Args:
            eventType: Filter by event type.
            agentName: Filter by agent name.
            correlationId: Filter by correlation ID.
            limit: Maximum events to return.

        Returns:
            List of matching events.
        """
        events = self._events

        if eventType:
            events = [
                e
                for e in events
                if e.eventType == eventType
                or (isinstance(e.eventType, TraceEventType) and e.eventType.value == eventType)
            ]

        if agentName:
            events = [e for e in events if e.agentName == agentName]

        if correlationId:
            events = [e for e in events if e.correlationId == correlationId]

        if limit:
            events = events[-limit:]

        return events

    def getInteractionTrace(self, correlationId: str) -> dict[str, Any]:
        """Get a full interaction trace by correlation ID.

        Args:
            correlationId: Correlation ID.

        Returns:
            Dict with interaction details and timing.
        """
        events = self.getEvents(correlationId=correlationId)

        if not events:
            return {"correlationId": correlationId, "events": []}

        # Calculate total duration
        startEvent = next(
            (e for e in events if e.eventType == TraceEventType.INTERACTION_START),
            None,
        )
        endEvent = next(
            (e for e in events if e.eventType == TraceEventType.INTERACTION_END),
            None,
        )

        totalDuration = endEvent.duration if endEvent else None

        return {
            "correlationId": correlationId,
            "events": [e.toDict() for e in events],
            "totalDuration": totalDuration,
            "eventCount": len(events),
        }

    def getStats(self) -> dict[str, Any]:
        """Get tracing statistics.

        Returns:
            Dict with statistics.
        """
        eventCounts: dict[str, int] = {}
        for event in self._events:
            key = event.eventType if isinstance(event.eventType, str) else event.eventType.value
            eventCounts[key] = eventCounts.get(key, 0) + 1

        # Calculate timing stats for LLM requests
        llmDurations = [
            e.duration
            for e in self._events
            if e.eventType == TraceEventType.LLM_RESPONSE and e.duration
        ]

        llmStats = {}
        if llmDurations:
            llmStats = {
                "count": len(llmDurations),
                "avgDuration": sum(llmDurations) / len(llmDurations),
                "minDuration": min(llmDurations),
                "maxDuration": max(llmDurations),
            }

        return {
            "enabled": self._enabled,
            "totalEvents": len(self._events),
            "eventCounts": eventCounts,
            "llmStats": llmStats,
            "activeTimers": len(self._timers),
        }

    def clear(self) -> None:
        """Clear all recorded events."""
        self._events.clear()
        self._timers.clear()

    def export(self, path: Path | None = None) -> str:
        """Export trace to JSON.

        Args:
            path: Path to write file (None for return string only).

        Returns:
            JSON string of trace data.
        """
        data = {
            "exportTime": datetime.now().isoformat(),
            "stats": self.getStats(),
            "events": [e.toDict() for e in self._events],
        }

        jsonStr = json.dumps(data, indent=2, ensure_ascii=False)

        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(jsonStr)
            logger.info(f"Exported trace to {path}")

        return jsonStr

    def __len__(self) -> int:
        """Get number of recorded events."""
        return len(self._events)
