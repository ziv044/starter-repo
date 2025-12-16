"""Logging configuration for pm6.

Provides structured logging with consistent formatting and debug modes.
"""

import logging
import sys
from enum import Enum
from typing import Any

# pm6 logger hierarchy
PM6_LOGGER = "pm6"
CORE_LOGGER = "pm6.core"
STATE_LOGGER = "pm6.state"
COST_LOGGER = "pm6.cost"
LLM_LOGGER = "pm6.llm"
TESTING_LOGGER = "pm6.testing"
AGENTS_LOGGER = "pm6.agents"


class LogLevel(str, Enum):
    """Log levels for pm6."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PM6LogFormatter(logging.Formatter):
    """Custom formatter for pm6 logs.

    Provides consistent formatting with optional colors.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    def __init__(self, useColors: bool = True, includeTimestamp: bool = True):
        self._useColors = useColors
        self._includeTimestamp = includeTimestamp

        if includeTimestamp:
            fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            datefmt = "%Y-%m-%d %H:%M:%S"
        else:
            fmt = "[%(levelname)s] %(name)s: %(message)s"
            datefmt = None

        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with optional colors."""
        if self._useColors and sys.stdout.isatty():
            levelColor = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            record.levelname = f"{levelColor}{record.levelname}{reset}"

        return super().format(record)


def configureLogging(
    level: LogLevel | str = LogLevel.INFO,
    useColors: bool = True,
    includeTimestamp: bool = True,
    logFile: str | None = None,
    format: str | None = None,
) -> logging.Logger:
    """Configure pm6 logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        useColors: Whether to use colored output in terminal.
        includeTimestamp: Whether to include timestamps.
        logFile: Optional file path for log output.
        format: Optional custom format string.

    Returns:
        The configured pm6 root logger.
    """
    # Get root pm6 logger
    logger = logging.getLogger(PM6_LOGGER)

    # Convert string to LogLevel if needed
    if isinstance(level, str):
        level = LogLevel(level.upper())

    logger.setLevel(getattr(logging, level.value))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    consoleHandler = logging.StreamHandler(sys.stdout)
    if format:
        consoleHandler.setFormatter(logging.Formatter(format))
    else:
        consoleHandler.setFormatter(
            PM6LogFormatter(useColors=useColors, includeTimestamp=includeTimestamp)
        )
    logger.addHandler(consoleHandler)

    # File handler if specified
    if logFile:
        fileHandler = logging.FileHandler(logFile, encoding="utf-8")
        fileHandler.setFormatter(
            PM6LogFormatter(useColors=False, includeTimestamp=True)
        )
        logger.addHandler(fileHandler)

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def getLogger(name: str) -> logging.Logger:
    """Get a pm6 logger.

    Args:
        name: Logger name (will be prefixed with 'pm6.' if not already).

    Returns:
        Logger instance.
    """
    if not name.startswith("pm6."):
        name = f"pm6.{name}"
    return logging.getLogger(name)


def setLogLevel(level: LogLevel | str, loggerName: str | None = None) -> None:
    """Set log level for a specific logger or all pm6 loggers.

    Args:
        level: Log level to set.
        loggerName: Specific logger name (None for all pm6 loggers).
    """
    if isinstance(level, str):
        level = LogLevel(level.upper())

    levelValue = getattr(logging, level.value)

    if loggerName:
        logging.getLogger(loggerName).setLevel(levelValue)
    else:
        logging.getLogger(PM6_LOGGER).setLevel(levelValue)


def setDebugMode(
    enabled: bool = True,
    components: list[str] | None = None,
) -> None:
    """Enable or disable debug mode.

    Debug mode sets all specified components to DEBUG level.

    Args:
        enabled: Whether to enable debug mode.
        components: Specific components to debug (None for all).
    """
    level = LogLevel.DEBUG if enabled else LogLevel.INFO

    if components is None:
        # Set all pm6 loggers to debug
        setLogLevel(level)
    else:
        for component in components:
            setLogLevel(level, f"pm6.{component}")


class LogContext:
    """Context manager for temporary log level changes.

    Example:
        with LogContext(level=LogLevel.DEBUG):
            # Debug logging enabled
            pass
        # Back to original level
    """

    def __init__(
        self,
        level: LogLevel | str,
        loggerName: str = PM6_LOGGER,
    ):
        self._level = level
        self._loggerName = loggerName
        self._originalLevel: int | None = None

    def __enter__(self) -> "LogContext":
        logger = logging.getLogger(self._loggerName)
        self._originalLevel = logger.level

        if isinstance(self._level, str):
            self._level = LogLevel(self._level.upper())

        logger.setLevel(getattr(logging, self._level.value))
        return self

    def __exit__(self, *args: Any) -> None:
        if self._originalLevel is not None:
            logging.getLogger(self._loggerName).setLevel(self._originalLevel)


# Initialize default logging on import
_defaultLogger = logging.getLogger(PM6_LOGGER)
if not _defaultLogger.handlers:
    # Only configure if not already configured
    configureLogging(level=LogLevel.WARNING, useColors=True)
