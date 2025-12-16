"""Logging and debugging infrastructure for pm6.

Provides structured logging, debug modes, and tracing capabilities.
"""

from pm6.logging.config import (
    LogLevel,
    configureLogging,
    getLogger,
    setDebugMode,
    setLogLevel,
)
from pm6.logging.tracer import InteractionTracer, TraceEvent

__all__ = [
    "configureLogging",
    "getLogger",
    "setLogLevel",
    "setDebugMode",
    "LogLevel",
    "InteractionTracer",
    "TraceEvent",
]
