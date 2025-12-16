"""Agent management routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from simConfigGui.services.agent_service import (
    add_agent,
    get_agent,
    list_agents,
    remove_agent,
    update_agent,
)
from simConfigGui.services.simulation_service import get_simulation

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/simulations/<sim_name>/agents/")
def list_agents_view(sim_name: str):
    """List all agents in a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    agents = list_agents(sim_name)
    return render_template("agents/list.html", agents=agents, sim_name=sim_name)


@agents_bp.route("/simulations/<sim_name>/agents/add", methods=["GET", "POST"])
def add_agent_view(sim_name: str):
    """Add a new agent."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    if request.method == "POST":
        try:
            config_data = {
                "name": request.form.get("name", "").strip(),
                "role": request.form.get("role", "").strip(),
                "systemPrompt": request.form.get("systemPrompt", ""),
                "model": request.form.get("model", "claude-sonnet-4-20250514"),
                "memoryPolicy": request.form.get("memoryPolicy", "summary"),
                "controlledBy": request.form.get("controlledBy", "cpu"),
                "initiative": float(request.form.get("initiative", 0.5)),
            }

            if not config_data["name"]:
                flash("Agent name is required", "error")
                return render_template("agents/form.html", sim_name=sim_name, agent=None)

            if not config_data["role"]:
                flash("Agent role is required", "error")
                return render_template("agents/form.html", sim_name=sim_name, agent=None)

            add_agent(sim_name, config_data)
            flash(f"Agent '{config_data['name']}' added successfully", "success")
            return redirect(url_for("agents.list_agents_view", sim_name=sim_name))

        except Exception as e:
            flash(f"Error adding agent: {e}", "error")
            return render_template("agents/form.html", sim_name=sim_name, agent=None)

    return render_template("agents/form.html", sim_name=sim_name, agent=None)


@agents_bp.route("/simulations/<sim_name>/agents/<agent_name>/edit", methods=["GET", "POST"])
def edit_agent_view(sim_name: str, agent_name: str):
    """Edit an existing agent."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    agent = get_agent(sim_name, agent_name)
    if not agent:
        flash(f"Agent '{agent_name}' not found", "error")
        return redirect(url_for("agents.list_agents_view", sim_name=sim_name))

    if request.method == "POST":
        try:
            config_data = {
                "name": agent_name,  # Name cannot be changed
                "role": request.form.get("role", "").strip(),
                "systemPrompt": request.form.get("systemPrompt", ""),
                "model": request.form.get("model", "claude-sonnet-4-20250514"),
                "memoryPolicy": request.form.get("memoryPolicy", "summary"),
                "controlledBy": request.form.get("controlledBy", "cpu"),
                "initiative": float(request.form.get("initiative", 0.5)),
            }

            update_agent(sim_name, config_data)
            flash(f"Agent '{agent_name}' updated successfully", "success")
            return redirect(url_for("agents.list_agents_view", sim_name=sim_name))

        except Exception as e:
            flash(f"Error updating agent: {e}", "error")

    return render_template("agents/form.html", sim_name=sim_name, agent=agent)


@agents_bp.route("/simulations/<sim_name>/agents/<agent_name>/delete", methods=["POST"])
def delete_agent_view(sim_name: str, agent_name: str):
    """Delete an agent."""
    if remove_agent(sim_name, agent_name):
        flash(f"Agent '{agent_name}' deleted", "success")
    else:
        flash(f"Failed to delete agent '{agent_name}'", "error")

    return redirect(url_for("agents.list_agents_view", sim_name=sim_name))
