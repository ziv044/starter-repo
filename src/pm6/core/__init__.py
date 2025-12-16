"""Core module for pm6 simulation engine.

Provides the main Simulation class, response types, rules, and turn-based engine.
"""

from pm6.core.response import AgentResponse, InteractionResult
from pm6.core.rules import Rule, RuleType, SimulationRules
from pm6.core.simulation import Simulation
from pm6.core.engine import SimulationEngine
from pm6.core.events import EventBus, Events
from pm6.core.types import (
    ActionType,
    AgentAction,
    EngineState,
    Event,
    ScheduledEvent,
    TurnResult,
)

__all__ = [
    # Core simulation
    "Simulation",
    "SimulationEngine",
    # Events
    "EventBus",
    "Events",
    # Response types
    "AgentResponse",
    "InteractionResult",
    # Rules
    "SimulationRules",
    "Rule",
    "RuleType",
    # Engine types
    "ActionType",
    "AgentAction",
    "EngineState",
    "Event",
    "ScheduledEvent",
    "TurnResult",
]
