"""pm6 - LLM-powered simulation engine with cost optimization.

This package provides infrastructure for building cost-effective,
AI-driven simulations using Anthropic's Claude models.

Example:
    >>> from pm6 import Simulation, AgentConfig
    >>> sim = Simulation("my_simulation")
    >>> sim.registerAgent(AgentConfig(name="pm", role="Prime Minister"))
    >>> response = sim.interact("pm", "What's your budget plan?")

Test Mode Example:
    >>> from pm6 import Simulation, AgentConfig
    >>> sim = Simulation.createTestSimulation(responses=["Mock response"])
    >>> sim.registerAgent(AgentConfig(name="test", role="Test"))
    >>> response = sim.interact("test", "Hello")  # Returns mock response
"""

__version__ = "0.1.0"

__all__ = [
    # Core
    "Simulation",
    "AgentResponse",
    "InteractionResult",
    "SimulationRules",
    "Rule",
    "RuleType",
    # Agents
    "AgentConfig",
    "MemoryPolicy",
    # Cost
    "TokenBudget",
    "TokenBudgetManager",
    # State
    "SessionRecorder",
    "SessionReplayer",
    # Testing
    "MockAnthropicClient",
    "MockResponse",
    # Logging
    "configureLogging",
    "getLogger",
    "LogLevel",
    "InteractionTracer",
    # Metrics
    "PerformanceTracker",
    "InteractionMetrics",
    "PerformanceBaseline",
    # Tools
    "Tool",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    # Exceptions
    "PM6Error",
    "AgentNotFoundError",
    "CostLimitError",
    "SignatureMatchError",
    "SessionNotFoundError",
    "ConfigurationError",
    "StorageError",
    "SimulationError",
    "RuleViolationError",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "Simulation":
        from pm6.core.simulation import Simulation

        return Simulation
    elif name in ("AgentResponse", "InteractionResult"):
        from pm6.core import response

        return getattr(response, name)
    elif name in ("SimulationRules", "Rule", "RuleType"):
        from pm6.core import rules

        return getattr(rules, name)
    elif name == "AgentConfig":
        from pm6.agents.agentConfig import AgentConfig

        return AgentConfig
    elif name == "MemoryPolicy":
        from pm6.agents.memoryPolicy import MemoryPolicy

        return MemoryPolicy
    elif name in ("TokenBudget", "TokenBudgetManager"):
        from pm6.cost import tokenBudget

        return getattr(tokenBudget, name)
    elif name in ("SessionRecorder", "SessionReplayer"):
        from pm6 import state

        return getattr(state, name)
    elif name in ("MockAnthropicClient", "MockResponse"):
        from pm6 import testing

        return getattr(testing, name)
    elif name in ("configureLogging", "getLogger", "LogLevel", "InteractionTracer"):
        from pm6 import logging as pm6_logging

        return getattr(pm6_logging, name)
    elif name in ("PerformanceTracker", "InteractionMetrics", "PerformanceBaseline"):
        from pm6 import metrics

        return getattr(metrics, name)
    elif name in ("Tool", "ToolCall", "ToolRegistry", "ToolResult"):
        from pm6 import tools

        return getattr(tools, name)
    elif name in __all__:
        from pm6 import exceptions

        return getattr(exceptions, name)
    raise AttributeError(f"module 'pm6' has no attribute '{name}'")
