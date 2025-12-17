"""Core module for pm6 simulation engine.

Provides the main Simulation class, response types, rules, and turn-based engine.

Note: Some imports are deferred to avoid circular dependencies.
Use explicit imports when needed:
    from pm6.core.simulation import Simulation
    from pm6.core.engine import SimulationEngine
"""

# Types can be imported immediately (no circular deps)
from pm6.core.types import (
    ActionType,
    AgentAction,
    Choice,
    EngineState,
    Event,
    PlayerInput,
    PlayModeOutput,
    ResponseFormatConfig,
    ResponseFormatType,
    ScheduledEvent,
    StateChange,
    TurnResult,
)


def __getattr__(name: str):
    """Lazy import for classes that have circular dependencies."""
    if name == "Simulation":
        from pm6.core.simulation import Simulation

        return Simulation
    if name == "SimulationEngine":
        from pm6.core.engine import SimulationEngine

        return SimulationEngine
    if name == "EventBus":
        from pm6.core.events import EventBus

        return EventBus
    if name == "Events":
        from pm6.core.events import Events

        return Events
    if name == "AgentResponse":
        from pm6.core.response import AgentResponse

        return AgentResponse
    if name == "InteractionResult":
        from pm6.core.response import InteractionResult

        return InteractionResult
    if name == "SimulationRules":
        from pm6.core.rules import SimulationRules

        return SimulationRules
    if name == "Rule":
        from pm6.core.rules import Rule

        return Rule
    if name == "RuleType":
        from pm6.core.rules import RuleType

        return RuleType
    if name == "PlayModeGenerator":
        from pm6.core.play_mode import PlayModeGenerator

        return PlayModeGenerator
    if name == "PlayModeStateTracker":
        from pm6.core.play_mode import PlayModeStateTracker

        return PlayModeStateTracker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core simulation (lazy loaded)
    "Simulation",
    "SimulationEngine",
    # Events (lazy loaded)
    "EventBus",
    "Events",
    # Response types (lazy loaded)
    "AgentResponse",
    "InteractionResult",
    # Rules (lazy loaded)
    "SimulationRules",
    "Rule",
    "RuleType",
    # Engine types (immediately available)
    "ActionType",
    "AgentAction",
    "EngineState",
    "Event",
    "ScheduledEvent",
    "TurnResult",
    # Play Mode types (immediately available)
    "Choice",
    "PlayerInput",
    "PlayModeOutput",
    "PlayModeGenerator",
    "PlayModeStateTracker",
    "ResponseFormatConfig",
    "ResponseFormatType",
    "StateChange",
]
