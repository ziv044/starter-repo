"""Service layer for event injection."""

import json
from typing import Any

from pm6.core.events import Events

from simConfigGui.services.simulation_service import get_simulation

# Standard event types for the UI
STANDARD_EVENTS = [
    Events.TURN_START,
    Events.TURN_END,
    Events.AGENT_SPOKE,
    Events.AGENT_ACTED,
    Events.STATE_CHANGED,
    Events.SIMULATION_START,
    Events.SIMULATION_END,
]


def inject_event(
    sim_name: str,
    event_name: str,
    data: dict[str, Any] | None = None,
    source: str = "admin",
) -> dict[str, Any] | None:
    """Inject an event into a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return None

    event = sim.injectEvent(event_name, data, source)
    return event.toDict()


def get_event_history(sim_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """Get recent event history."""
    sim = get_simulation(sim_name)
    if not sim:
        return []

    return sim.getEventHistory(limit)


def parse_event_data(data_str: str) -> dict[str, Any]:
    """Parse event data from form input."""
    if not data_str or data_str.strip() == "":
        return {}
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        return {"raw": data_str}
