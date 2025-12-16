"""Simulation management routes."""

import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from simConfigGui.services.config_generator import ConfigGenerator
from simConfigGui.services.simulation_service import (
    create_simulation,
    delete_simulation,
    get_simulation,
    get_simulation_state,
    list_simulations,
)
from simConfigGui.services.agent_service import add_agent

simulation_bp = Blueprint("simulation", __name__)


@simulation_bp.route("/")
def list_simulations_view():
    """List all simulations."""
    simulations = list_simulations()
    return render_template("simulations/list.html", simulations=simulations)


@simulation_bp.route("/create")
def create_simulation_view():
    """Mode selection for creating a new simulation."""
    return render_template("simulations/create.html")


@simulation_bp.route("/create/manual", methods=["GET", "POST"])
def create_manual():
    """Manual simulation creation."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        test_mode = request.form.get("test_mode") == "on"
        enable_cache = request.form.get("enable_cache") == "on"

        if not name:
            flash("Simulation name is required", "error")
            return render_template("simulations/manual.html")

        if name in current_app.simulations:
            flash(f"Simulation '{name}' already exists", "error")
            return render_template("simulations/manual.html")

        try:
            create_simulation(name, test_mode=test_mode, enable_cache=enable_cache)
            flash(f"Simulation '{name}' created successfully", "success")
            return redirect(url_for("simulation.view_simulation", name=name))
        except Exception as e:
            flash(f"Error creating simulation: {e}", "error")
            return render_template("simulations/manual.html")

    return render_template("simulations/manual.html")


@simulation_bp.route("/create/wizard")
def create_wizard():
    """AI-assisted simulation creation - mode selection."""
    return render_template("simulations/wizard_select.html")


@simulation_bp.route("/create/wizard/quick")
def create_wizard_quick():
    """Quick generation from single prompt."""
    templates = ConfigGenerator.get_templates()
    templates_with_prompts = []
    for t in templates:
        t["prompt"] = ConfigGenerator.get_template_prompt(t["name"]) or ""
        templates_with_prompts.append(t)
    return render_template("simulations/wizard.html", templates=templates_with_prompts)


@simulation_bp.route("/create/wizard/chat")
def create_wizard_chat():
    """Conversational wizard - start fresh conversation."""
    # Clear any existing conversation
    session.pop("wizard_conversation", None)
    session.pop("wizard_ready", None)
    return render_template("simulations/wizard_chat.html", conversation=[], ready=False)


@simulation_bp.route("/create/wizard/chat/send", methods=["POST"])
def wizard_chat_send():
    """Send a message in the conversational wizard."""
    user_message = request.form.get("message", "").strip()
    if not user_message:
        flash("Please enter a message", "error")
        return redirect(url_for("simulation.create_wizard_chat"))

    # Get or create conversation
    conversation = session.get("wizard_conversation", [])
    conversation.append({"role": "user", "content": user_message})

    try:
        generator = ConfigGenerator()
        result = generator.gather_info(conversation)

        # Add assistant response
        conversation.append({"role": "assistant", "content": result["message"]})

        # Save to session
        session["wizard_conversation"] = conversation
        session["wizard_ready"] = result["ready"]

        if result["ready"]:
            session["wizard_summary"] = result["summary"]

    except Exception as e:
        flash(f"Error: {e}", "error")

    return render_template(
        "simulations/wizard_chat.html",
        conversation=conversation,
        ready=session.get("wizard_ready", False),
    )


@simulation_bp.route("/create/wizard/chat/generate", methods=["POST"])
def wizard_chat_generate():
    """Generate config from conversation."""
    conversation = session.get("wizard_conversation", [])
    if not conversation:
        flash("No conversation to generate from", "error")
        return redirect(url_for("simulation.create_wizard_chat"))

    try:
        generator = ConfigGenerator()
        config = generator.generate_from_conversation(conversation)
        session["generated_config"] = config
        # Clean up wizard session data
        session.pop("wizard_conversation", None)
        session.pop("wizard_ready", None)
        session.pop("wizard_summary", None)
        return redirect(url_for("simulation.review_config"))
    except Exception as e:
        flash(f"Error generating config: {e}", "error")
        return redirect(url_for("simulation.create_wizard_chat"))


@simulation_bp.route("/create/generate", methods=["POST"])
def generate_config():
    """Generate configuration from prompt using AI."""
    prompt = request.form.get("prompt", "").strip()
    template = request.form.get("template", "").strip() or None

    if not prompt:
        flash("Please describe the simulation you want to create", "error")
        return redirect(url_for("simulation.create_wizard"))

    try:
        generator = ConfigGenerator()
        config = generator.generate_config(prompt, template_name=template)
        # Store in session for review
        session["generated_config"] = config
        return redirect(url_for("simulation.review_config"))
    except Exception as e:
        flash(f"Error generating configuration: {e}", "error")
        return redirect(url_for("simulation.create_wizard"))


@simulation_bp.route("/create/review", methods=["GET"])
def review_config():
    """Review generated configuration before applying."""
    config = session.get("generated_config")
    if not config:
        flash("No configuration to review. Please generate one first.", "error")
        return redirect(url_for("simulation.create_wizard"))
    return render_template("simulations/review.html", config=config)


@simulation_bp.route("/create/apply", methods=["POST"])
def apply_config():
    """Apply reviewed configuration to create simulation."""
    name = request.form.get("name", "").strip()
    test_mode = request.form.get("test_mode") == "on"
    enable_cache = request.form.get("enable_cache") == "on"

    if not name:
        flash("Simulation name is required", "error")
        return redirect(url_for("simulation.review_config"))

    if name in current_app.simulations:
        flash(f"Simulation '{name}' already exists", "error")
        return redirect(url_for("simulation.review_config"))

    try:
        # Create the simulation
        create_simulation(name, test_mode=test_mode, enable_cache=enable_cache)

        # Add entity agents
        entity_count = int(request.form.get("entity_agent_count", 0))
        for i in range(entity_count):
            agent_name = request.form.get(f"entity_agent_{i}_name")
            if not agent_name:
                continue
            agent_data = {
                "name": agent_name,
                "role": request.form.get(f"entity_agent_{i}_role", ""),
                "systemPrompt": request.form.get(f"entity_agent_{i}_systemPrompt", ""),
                "model": request.form.get(f"entity_agent_{i}_model", "claude-sonnet-4-20250514"),
                "memoryPolicy": request.form.get(f"entity_agent_{i}_memoryPolicy", "summary"),
                "controlledBy": request.form.get(f"entity_agent_{i}_controlledBy", "cpu"),
                "initiative": float(request.form.get(f"entity_agent_{i}_initiative", 0.5)),
                "agentType": "entity",
            }
            add_agent(name, agent_data)

        # Add operational agents
        op_count = int(request.form.get("op_agent_count", 0))
        for i in range(op_count):
            agent_name = request.form.get(f"op_agent_{i}_name")
            if not agent_name:
                continue
            agent_data = {
                "name": agent_name,
                "role": request.form.get(f"op_agent_{i}_role", ""),
                "systemPrompt": request.form.get(f"op_agent_{i}_systemPrompt", ""),
                "model": request.form.get(f"op_agent_{i}_model", "claude-sonnet-4-20250514"),
                "memoryPolicy": request.form.get(f"op_agent_{i}_memoryPolicy", "summary"),
                "controlledBy": "cpu",
                "initiative": float(request.form.get(f"op_agent_{i}_initiative", 0.3)),
                "agentType": "operational",
                "function": request.form.get(f"op_agent_{i}_function", "custom"),
            }
            add_agent(name, agent_data)

        # Set world state
        world_state_json = request.form.get("world_state", "{}")
        try:
            world_state = json.loads(world_state_json)
            sim = get_simulation(name)
            if sim:
                sim.setWorldState(world_state)
        except json.JSONDecodeError:
            flash("Warning: Could not parse world state JSON", "warning")

        # Clear session
        session.pop("generated_config", None)

        flash(f"Simulation '{name}' created successfully with {entity_count} entity agents and {op_count} operational agents", "success")
        return redirect(url_for("simulation.view_simulation", name=name))

    except Exception as e:
        flash(f"Error creating simulation: {e}", "error")
        return redirect(url_for("simulation.review_config"))


@simulation_bp.route("/<name>")
def view_simulation(name: str):
    """View simulation details."""
    state = get_simulation_state(name)
    if not state:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    return render_template("simulations/detail.html", sim=state, sim_name=name)


@simulation_bp.route("/<name>/delete", methods=["POST"])
def delete_simulation_view(name: str):
    """Delete a simulation."""
    if delete_simulation(name):
        flash(f"Simulation '{name}' deleted", "success")
    else:
        flash(f"Simulation '{name}' not found", "error")

    return redirect(url_for("simulation.list_simulations_view"))


@simulation_bp.route("/<name>/state", methods=["GET", "POST"])
def edit_state(name: str):
    """View and edit world state."""
    sim = get_simulation(name)
    if not sim:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    if request.method == "POST":
        try:
            state_json = request.form.get("state", "{}")
            new_state = json.loads(state_json)
            sim.setWorldState(new_state)
            flash("World state updated", "success")
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "error")
        except Exception as e:
            flash(f"Error updating state: {e}", "error")

    current_state = sim.getWorldState()
    return render_template(
        "simulations/state.html",
        sim_name=name,
        state=current_state,
        state_json=json.dumps(current_state, indent=2),
    )
