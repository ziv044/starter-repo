"""Custom exceptions for pm6."""


class PM6Error(Exception):
    """Base exception for all pm6 errors."""

    pass


class ReplayNotFoundError(PM6Error):
    """Raised when replay data is not found for a request.

    Args:
        agent_name: The agent that made the request.
        call_index: The call index that was not found.
    """

    def __init__(self, agent_name: str, call_index: int) -> None:
        self.agent_name = agent_name
        self.call_index = call_index
        super().__init__(
            f"No replay data found for agent '{agent_name}' at call index {call_index}"
        )


class SessionNotFoundError(PM6Error):
    """Raised when a session file is not found.

    Args:
        session_path: The path to the session file that was not found.
    """

    def __init__(self, session_path: str) -> None:
        self.session_path = session_path
        super().__init__(f"Session file not found: {session_path}")
