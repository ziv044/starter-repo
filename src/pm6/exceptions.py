"""pm6 exception hierarchy.

All pm6 exceptions inherit from PM6Error for easy catching.
"""


class PM6Error(Exception):
    """Base exception for all pm6 errors."""

    pass


class AgentNotFoundError(PM6Error):
    """Raised when a requested agent doesn't exist in the simulation."""

    def __init__(self, agentName: str):
        self.agentName = agentName
        super().__init__(f"Agent '{agentName}' not found in simulation")


class CostLimitError(PM6Error):
    """Raised when an operation would exceed cost limits."""

    def __init__(self, limit: float, current: float, requested: float):
        self.limit = limit
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cost limit exceeded: limit={limit}, current={current}, requested={requested}"
        )


class SignatureMatchError(PM6Error):
    """Raised when signature lookup fails in strict mode."""

    def __init__(self, signature: str):
        self.signature = signature
        super().__init__(f"No cached response found for signature: {signature}")


class SessionNotFoundError(PM6Error):
    """Raised when a requested session or checkpoint doesn't exist."""

    def __init__(self, sessionName: str, checkpoint: str | None = None):
        self.sessionName = sessionName
        self.checkpoint = checkpoint
        if checkpoint:
            msg = f"Checkpoint '{checkpoint}' not found in session '{sessionName}'"
        else:
            msg = f"Session '{sessionName}' not found"
        super().__init__(msg)


class ConfigurationError(PM6Error):
    """Raised when configuration is invalid or missing."""

    pass


class StorageError(PM6Error):
    """Raised when storage operations fail."""

    pass


class SimulationError(PM6Error):
    """Raised when simulation operations fail."""

    pass


class RuleViolationError(PM6Error):
    """Raised when a simulation rule is violated."""

    def __init__(self, ruleName: str, message: str):
        self.ruleName = ruleName
        super().__init__(f"Rule '{ruleName}' violated: {message}")
