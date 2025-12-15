"""LLM Logger for recording Claude API calls to JSONL files."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


class LLMLogger:
    """Logger for recording Claude API calls to JSONL files.

    Attributes:
        session_name: Name of the current logging session.
        session_path: Path to the JSONL log file.
    """

    def __init__(self, session_name: str) -> None:
        """Initialize the logger with a session name.

        Args:
            session_name: Base name for the session file.
                         Will be auto-incremented if file exists.
        """
        self.session_name = session_name
        self.session_path = self._get_session_path(session_name)
        self._call_counts: dict[str, int] = {}

    def _get_session_path(self, session_name: str) -> Path:
        """Get the path for a session file, auto-incrementing if needed.

        Args:
            session_name: Base name for the session.

        Returns:
            Path to the session file with incremented suffix.
        """
        settings = get_settings()
        log_dir = settings.log_dir

        # Find next available increment
        counter = 1
        while True:
            path = log_dir / f"{session_name}_{counter:03d}.jsonl"
            if not path.exists():
                return path
            counter += 1

    def log(
        self,
        agent_name: str,
        request: dict[str, Any],
        response: dict[str, Any],
        duration_ms: int,
    ) -> None:
        """Log a Claude API call.

        Args:
            agent_name: Name of the agent making the call.
            request: The request sent to the API.
            response: The response received from the API.
            duration_ms: Duration of the call in milliseconds.
        """
        # Track call count per agent
        self._call_counts[agent_name] = self._call_counts.get(agent_name, 0) + 1

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": agent_name,
            "call_index": self._call_counts[agent_name],
            "request": request,
            "response": response,
            "duration_ms": duration_ms,
        }

        with open(self.session_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def get_call_count(self, agent_name: str) -> int:
        """Get the number of calls logged for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Number of calls logged for the agent.
        """
        return self._call_counts.get(agent_name, 0)


class LoggedCall:
    """Context manager for timing and logging API calls.

    Usage:
        with LoggedCall(logger, "my_agent", request) as call:
            response = client.messages.create(**request)
            call.set_response(response)
    """

    def __init__(
        self, logger: LLMLogger, agent_name: str, request: dict[str, Any]
    ) -> None:
        """Initialize the logged call context.

        Args:
            logger: The LLMLogger instance.
            agent_name: Name of the agent making the call.
            request: The request being sent.
        """
        self.logger = logger
        self.agent_name = agent_name
        self.request = request
        self._response: dict[str, Any] | None = None
        self._start_time: float = 0

    def __enter__(self) -> "LoggedCall":
        """Start timing the call."""
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Log the call on exit."""
        duration_ms = int((time.perf_counter() - self._start_time) * 1000)
        if self._response is not None:
            self.logger.log(
                self.agent_name, self.request, self._response, duration_ms
            )

    def set_response(self, response: Any) -> None:
        """Set the response to be logged.

        Args:
            response: The API response (will be converted to dict).
        """
        if hasattr(response, "model_dump"):
            self._response = response.model_dump()
        elif isinstance(response, dict):
            self._response = response
        else:
            self._response = {"raw": str(response)}
