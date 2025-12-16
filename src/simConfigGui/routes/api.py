"""JSON API routes for AJAX refresh."""

from flask import Blueprint, jsonify

from simConfigGui.services.agent_service import list_agents
from simConfigGui.services.event_service import get_event_history
from simConfigGui.services.simulation_service import (
    get_simulation,
    get_simulation_state,
    list_simulations,
)

api_bp = Blueprint("api", __name__)


@api_bp.route("/simulations")
def api_list_simulations():
    """List all simulations."""
    simulations = list_simulations()
    return jsonify({"success": True, "simulations": simulations})


@api_bp.route("/simulations/<name>")
def api_get_simulation(name: str):
    """Get simulation details."""
    state = get_simulation_state(name)
    if not state:
        return jsonify({"success": False, "error": "Simulation not found"}), 404
    return jsonify({"success": True, "simulation": state})


@api_bp.route("/simulations/<name>/agents")
def api_list_agents(name: str):
    """List agents in a simulation."""
    sim = get_simulation(name)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    agents = list_agents(name)
    return jsonify({"success": True, "agents": agents})


@api_bp.route("/simulations/<name>/events/history")
def api_event_history(name: str):
    """Get event history."""
    sim = get_simulation(name)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    events = get_event_history(name)
    return jsonify({"success": True, "events": events})


@api_bp.route("/simulations/<name>/stats")
def api_simulation_stats(name: str):
    """Get simulation statistics."""
    sim = get_simulation(name)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    stats = sim.getStats()
    return jsonify({"success": True, "stats": stats})


@api_bp.route("/simulations/<name>/state")
def api_simulation_state(name: str):
    """Get world state."""
    sim = get_simulation(name)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    state = sim.getWorldState()
    return jsonify({"success": True, "state": state})
