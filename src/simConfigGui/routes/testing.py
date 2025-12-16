"""Testing routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from simConfigGui.services.agent_service import list_agents
from simConfigGui.services.simulation_service import get_simulation
from simConfigGui.services.test_service import (
    get_interaction_history,
    get_mock_call_history,
    reset_mock_state,
    run_interaction,
)

testing_bp = Blueprint("testing", __name__)


@testing_bp.route("/simulations/<sim_name>/testing/")
def testing_page(sim_name: str):
    """Test runner page."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    agents = list_agents(sim_name)
    history = get_interaction_history(sim_name)
    mock_history = get_mock_call_history(sim_name)

    return render_template(
        "testing/runner.html",
        sim_name=sim_name,
        agents=agents,
        history=history,
        mock_history=mock_history,
        is_test_mode=sim.isTestMode,
    )


@testing_bp.route("/simulations/<sim_name>/testing/run", methods=["POST"])
def run_test(sim_name: str):
    """Run a test interaction."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    agent_name = request.form.get("agentName", "").strip()
    user_input = request.form.get("userInput", "").strip()
    mock_response = request.form.get("mockResponse", "").strip() or None
    force_live = request.form.get("forceLive") == "on"

    if not agent_name:
        flash("Agent name is required", "error")
        return redirect(url_for("testing.testing_page", sim_name=sim_name))

    if not user_input:
        flash("User input is required", "error")
        return redirect(url_for("testing.testing_page", sim_name=sim_name))

    result = run_interaction(sim_name, agent_name, user_input, mock_response, force_live)

    if result and result.get("success"):
        mode_label = "[LIVE]" if result.get("wasLive") else "[MOCK]"
        flash(f"{mode_label} Response from {result['agentName']}: {result['content'][:100]}...", "success")
    elif result:
        flash(f"Test failed: {result.get('error', 'Unknown error')}", "error")
    else:
        flash("Failed to run test", "error")

    return redirect(url_for("testing.testing_page", sim_name=sim_name))


@testing_bp.route("/simulations/<sim_name>/testing/reset", methods=["POST"])
def reset_test(sim_name: str):
    """Reset mock state."""
    if reset_mock_state(sim_name):
        flash("Mock state reset successfully", "success")
    else:
        flash("Failed to reset mock state (simulation not in test mode?)", "error")

    return redirect(url_for("testing.testing_page", sim_name=sim_name))


@testing_bp.route("/simulations/<sim_name>/testing/results")
def test_results(sim_name: str):
    """View test results."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    history = get_interaction_history(sim_name)
    mock_history = get_mock_call_history(sim_name)

    return render_template(
        "testing/results.html",
        sim_name=sim_name,
        history=history,
        mock_history=mock_history,
    )
