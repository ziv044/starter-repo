"""Service layer for agent management."""

from typing import Any

from pm6 import AgentConfig, MemoryPolicy

from simConfigGui.services.simulation_service import get_simulation


def get_agent(sim_name: str, agent_name: str) -> AgentConfig | None:
    """Get an agent from a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return None
    try:
        return sim.getAgent(agent_name)
    except Exception:
        return None


def list_agents(sim_name: str) -> list[dict[str, Any]]:
    """List all agents in a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return []

    return [sim.getAgent(name).toDict() for name in sim.listAgents()]


def add_agent(sim_name: str, config_data: dict[str, Any]) -> AgentConfig | None:
    """Add an agent to a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return None

    # Convert memoryPolicy string to enum
    if "memoryPolicy" in config_data and isinstance(config_data["memoryPolicy"], str):
        config_data["memoryPolicy"] = MemoryPolicy(config_data["memoryPolicy"])

    # Handle agent type metadata
    agent_type = config_data.pop("agentType", "entity")
    function = config_data.pop("function", None)
    config_data["metadata"] = {
        "agentType": agent_type,
    }
    if agent_type == "operational" and function:
        config_data["metadata"]["function"] = function

    config = AgentConfig(**config_data)
    sim.registerAgent(config)
    return config


def update_agent(sim_name: str, config_data: dict[str, Any]) -> AgentConfig | None:
    """Update an agent in a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return None

    # Convert memoryPolicy string to enum
    if "memoryPolicy" in config_data and isinstance(config_data["memoryPolicy"], str):
        config_data["memoryPolicy"] = MemoryPolicy(config_data["memoryPolicy"])

    # Handle agent type metadata
    agent_type = config_data.pop("agentType", "entity")
    function = config_data.pop("function", None)
    config_data["metadata"] = {
        "agentType": agent_type,
    }
    if agent_type == "operational" and function:
        config_data["metadata"]["function"] = function

    config = AgentConfig(**config_data)
    sim.updateAgent(config)
    return config


def remove_agent(sim_name: str, agent_name: str) -> bool:
    """Remove an agent from a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return False

    try:
        sim.removeAgent(agent_name)
        return True
    except Exception:
        return False
