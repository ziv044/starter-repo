"""Service layer for simulation management."""

from typing import Any

from flask import current_app

from pm6 import Simulation


def get_simulation(name: str) -> Simulation | None:
    """Get a simulation by name."""
    return current_app.simulations.get(name)


def create_simulation(
    name: str,
    test_mode: bool = False,
    enable_cache: bool = True,
) -> Simulation:
    """Create a new simulation."""
    sim = Simulation(
        name=name,
        dbPath=current_app.db_path,
        testMode=test_mode,
        enableCache=enable_cache,
    )
    current_app.simulations[name] = sim
    return sim


def delete_simulation(name: str) -> bool:
    """Delete a simulation."""
    if name in current_app.simulations:
        del current_app.simulations[name]
        return True
    return False


def list_simulations() -> list[dict[str, Any]]:
    """List all simulations with basic info."""
    return [
        {
            "name": name,
            "agentCount": len(sim.listAgents()),
            "turnCount": sim.turnCount,
            "isTestMode": sim.isTestMode,
        }
        for name, sim in current_app.simulations.items()
    ]


def get_simulation_state(name: str) -> dict[str, Any] | None:
    """Get full simulation state."""
    sim = get_simulation(name)
    if not sim:
        return None

    return {
        "name": sim.name,
        "worldState": sim.getWorldState(),
        "agents": [sim.getAgent(a).toDict() for a in sim.listAgents()],
        "stats": sim.getStats(),
        "turnCount": sim.turnCount,
        "isTestMode": sim.isTestMode,
        "isCacheEnabled": sim.isCacheEnabled,
    }
