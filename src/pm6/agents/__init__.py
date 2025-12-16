"""Agent system module for pm6.

Provides agent configuration, memory policies, routing, relevance detection,
and state updates.
"""

from pm6.agents.agentConfig import AgentConfig
from pm6.agents.memoryPolicy import MemoryManager, MemoryPolicy
from pm6.agents.relevance import (
    AgentRelevanceDetector,
    RelevanceRule,
    RelevanceScore,
    RelevanceStrategy,
)
from pm6.agents.routing import AgentRouter
from pm6.agents.stateUpdater import (
    AgentStateUpdater,
    StateUpdate,
    UpdateRule,
    UpdateTrigger,
    extractBoolean,
    extractNumber,
)

__all__ = [
    "AgentConfig",
    "MemoryPolicy",
    "MemoryManager",
    "AgentRouter",
    "AgentRelevanceDetector",
    "RelevanceRule",
    "RelevanceScore",
    "RelevanceStrategy",
    "AgentStateUpdater",
    "StateUpdate",
    "UpdateRule",
    "UpdateTrigger",
    "extractNumber",
    "extractBoolean",
]
