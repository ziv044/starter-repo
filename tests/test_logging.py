"""Tests for the logging module."""

import logging

import pytest

from pm6.logging import (
    InteractionTracer,
    LogLevel,
    TraceEvent,
    configureLogging,
    getLogger,
    setDebugMode,
    setLogLevel,
)
from pm6.logging.tracer import TraceEventType


class TestLoggingConfig:
    """Tests for logging configuration."""

    def test_configure_logging(self):
        """Test basic logging configuration."""
        logger = configureLogging(level=LogLevel.INFO, useColors=False)

        assert logger.name == "pm6"
        assert logger.level == logging.INFO

    def test_get_logger(self):
        """Test getting a pm6 logger."""
        logger = getLogger("test")
        assert logger.name == "pm6.test"

        # Already prefixed name
        logger2 = getLogger("pm6.test2")
        assert logger2.name == "pm6.test2"

    def test_set_log_level(self):
        """Test setting log level."""
        setLogLevel(LogLevel.DEBUG)
        logger = logging.getLogger("pm6")
        assert logger.level == logging.DEBUG

        setLogLevel("WARNING")
        assert logger.level == logging.WARNING

    def test_set_debug_mode(self):
        """Test enabling debug mode."""
        setDebugMode(True)
        logger = logging.getLogger("pm6")
        assert logger.level == logging.DEBUG

        setDebugMode(False)
        assert logger.level == logging.INFO


class TestInteractionTracer:
    """Tests for InteractionTracer."""

    def test_record_event(self):
        """Test recording a trace event."""
        tracer = InteractionTracer()

        event = tracer.record(
            TraceEventType.INTERACTION_START,
            data={"agentName": "TestAgent"},
        )

        assert event.eventType == TraceEventType.INTERACTION_START
        assert event.data["agentName"] == "TestAgent"
        assert len(tracer) == 1

    def test_disabled_tracer(self):
        """Test disabled tracer doesn't record."""
        tracer = InteractionTracer(enabled=False)

        tracer.record(TraceEventType.INTERACTION_START)

        assert len(tracer) == 0

    def test_enable_disable(self):
        """Test enabling and disabling."""
        tracer = InteractionTracer(enabled=True)
        assert tracer.isEnabled

        tracer.disable()
        assert not tracer.isEnabled

        tracer.enable()
        assert tracer.isEnabled

    def test_correlation_id(self):
        """Test correlation ID generation."""
        tracer = InteractionTracer()

        id1 = tracer.newCorrelationId()
        id2 = tracer.newCorrelationId()

        assert id1 != id2
        assert id1.startswith("trace_")

    def test_timer_recording(self):
        """Test timed event recording."""
        tracer = InteractionTracer()

        timerId = tracer.startTimer("test")
        # Do something
        event = tracer.recordTimed(
            TraceEventType.LLM_RESPONSE,
            timerId,
            data={"model": "test"},
        )

        assert event.duration is not None
        assert event.duration >= 0

    def test_get_events_filtered(self):
        """Test filtering events."""
        tracer = InteractionTracer()

        tracer.record(TraceEventType.INTERACTION_START, agentName="Agent1")
        tracer.record(TraceEventType.CACHE_HIT, agentName="Agent1")
        tracer.record(TraceEventType.INTERACTION_START, agentName="Agent2")

        # Filter by type
        starts = tracer.getEvents(eventType=TraceEventType.INTERACTION_START)
        assert len(starts) == 2

        # Filter by agent
        agent1Events = tracer.getEvents(agentName="Agent1")
        assert len(agent1Events) == 2

    def test_get_events_with_limit(self):
        """Test event limiting."""
        tracer = InteractionTracer()

        for i in range(10):
            tracer.record(TraceEventType.CUSTOM, data={"index": i})

        events = tracer.getEvents(limit=5)
        assert len(events) == 5

    def test_get_interaction_trace(self):
        """Test getting a full interaction trace."""
        tracer = InteractionTracer()
        corrId = tracer.newCorrelationId()

        tracer.record(TraceEventType.INTERACTION_START, correlationId=corrId)
        tracer.record(TraceEventType.CACHE_LOOKUP, correlationId=corrId)
        tracer.record(TraceEventType.INTERACTION_END, correlationId=corrId)

        trace = tracer.getInteractionTrace(corrId)

        assert trace["correlationId"] == corrId
        assert trace["eventCount"] == 3

    def test_get_stats(self):
        """Test getting trace statistics."""
        tracer = InteractionTracer()

        tracer.record(TraceEventType.INTERACTION_START)
        tracer.record(TraceEventType.INTERACTION_END)
        tracer.record(TraceEventType.CACHE_HIT)

        stats = tracer.getStats()

        assert stats["enabled"]
        assert stats["totalEvents"] == 3
        assert "eventCounts" in stats

    def test_clear(self):
        """Test clearing events."""
        tracer = InteractionTracer()

        tracer.record(TraceEventType.INTERACTION_START)
        tracer.record(TraceEventType.INTERACTION_END)

        assert len(tracer) == 2

        tracer.clear()
        assert len(tracer) == 0

    def test_export(self, tmp_path):
        """Test exporting trace."""
        tracer = InteractionTracer()

        tracer.record(TraceEventType.INTERACTION_START, data={"test": True})

        # Export to string
        jsonStr = tracer.export()
        assert "events" in jsonStr
        assert "interaction_start" in jsonStr  # Uses enum value (snake_case)

        # Export to file
        path = tmp_path / "trace.json"
        tracer.export(path)
        assert path.exists()

    def test_max_events_limit(self):
        """Test max events trimming."""
        tracer = InteractionTracer(maxEvents=5)

        for i in range(10):
            tracer.record(TraceEventType.CUSTOM, data={"index": i})

        assert len(tracer) == 5
        # Should have last 5 events
        events = tracer.getEvents()
        assert events[0].data["index"] == 5


class TestTraceEvent:
    """Tests for TraceEvent."""

    def test_create_event(self):
        """Test creating a trace event."""
        event = TraceEvent(
            eventType=TraceEventType.INTERACTION_START,
            data={"key": "value"},
            agentName="TestAgent",
        )

        assert event.eventType == TraceEventType.INTERACTION_START
        assert event.data["key"] == "value"
        assert event.agentName == "TestAgent"

    def test_to_dict(self):
        """Test converting to dictionary."""
        event = TraceEvent(
            eventType=TraceEventType.CACHE_HIT,
            data={"signature": "abc123"},
        )

        d = event.toDict()

        assert d["eventType"] == "cache_hit"
        assert d["data"]["signature"] == "abc123"
