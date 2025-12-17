"""Simulation management routes."""

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

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


# Helper functions for storing large configs (Flask sessions have 4KB limit)
def _get_config_path() -> Path:
    """Get path for temporary config storage."""
    return current_app.db_path / ".temp_configs"


def _store_config(config: dict) -> str:
    """Store config to temp file, return config ID."""
    config_dir = _get_config_path()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_id = str(uuid.uuid4())
    config_path = config_dir / f"{config_id}.json"
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_id


def _load_config(config_id: str) -> dict | None:
    """Load config from temp file."""
    if not config_id:
        return None
    config_path = _get_config_path() / f"{config_id}.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return None


def _delete_config(config_id: str) -> None:
    """Delete temp config file."""
    if not config_id:
        return
    config_path = _get_config_path() / f"{config_id}.json"
    if config_path.exists():
        config_path.unlink()


def _save_pipeline_log(sim_name: str, result: dict, run_type: str = "execute") -> Path:
    """Save pipeline execution result to logs/pipelines.

    Args:
        sim_name: Name of the simulation.
        result: Pipeline execution result dict.
        run_type: Type of run (execute, dry-run, step).

    Returns:
        Path to the saved log file.
    """
    logs_dir = Path("logs") / "pipelines" / sim_name
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{run_type}.json"
    log_path = logs_dir / filename

    log_data = {
        "simulation": sim_name,
        "runType": run_type,
        "timestamp": datetime.now().isoformat(),
        "result": result,
    }

    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    return log_path


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
        # Store config in file (session has 4KB limit)
        config_id = _store_config(config)
        session["config_id"] = config_id
        session.modified = True
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
        # Store config in file (session has 4KB limit)
        config_id = _store_config(config)
        session["config_id"] = config_id
        session.modified = True
        return redirect(url_for("simulation.review_config"))
    except Exception as e:
        flash(f"Error generating configuration: {e}", "error")
        return redirect(url_for("simulation.create_wizard"))


@simulation_bp.route("/create/review", methods=["GET"])
def review_config():
    """Review generated configuration before applying."""
    config_id = session.get("config_id")
    config = _load_config(config_id)
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

        # Set pipeline config if provided
        pipeline_json = request.form.get("pipeline_config", "")
        if pipeline_json:
            try:
                from pm6.core.types import PipelineConfig
                pipeline_data = json.loads(pipeline_json)
                pipeline_config = PipelineConfig.fromDict(pipeline_data)
                sim = get_simulation(name)
                if sim:
                    sim.setPipelineConfig(pipeline_config)
            except (json.JSONDecodeError, Exception) as e:
                flash(f"Warning: Could not set pipeline config: {e}", "warning")

        # Clear session and temp files
        config_id = session.pop("config_id", None)
        _delete_config(config_id)

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


@simulation_bp.route("/<name>/toggle-test-mode", methods=["POST"])
def toggle_test_mode(name: str):
    """Toggle simulation between test mode and real LLM mode."""
    sim = get_simulation(name)
    if not sim:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    new_mode = not sim.isTestMode
    sim.setTestMode(new_mode)

    mode_name = "Test Mode (Mock LLM)" if new_mode else "Real LLM Mode"
    flash(f"Switched to {mode_name}", "success")

    return redirect(url_for("simulation.view_simulation", name=name))


@simulation_bp.route("/<name>/toggle-cache", methods=["POST"])
def toggle_cache(name: str):
    """Toggle response caching on/off."""
    sim = get_simulation(name)
    if not sim:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    new_state = not sim.isCacheEnabled
    sim.setCacheEnabled(new_state)

    state_name = "enabled" if new_state else "disabled"
    flash(f"Response cache {state_name}", "success")

    return redirect(url_for("simulation.view_simulation", name=name))


@simulation_bp.route("/<name>/clear-cache", methods=["POST"])
def clear_cache(name: str):
    """Clear all cached responses for a simulation."""
    sim = get_simulation(name)
    if not sim:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    if sim._responseCache:
        sim._responseCache.clear()
        flash("Response cache cleared", "success")
    else:
        # Clear from disk even if cache is disabled
        import shutil
        cache_path = current_app.db_path / name / "responses"
        if cache_path.exists():
            shutil.rmtree(cache_path)
            flash("Response cache files deleted", "success")
        else:
            flash("No cache to clear", "info")

    return redirect(url_for("simulation.view_simulation", name=name))


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


# =============================================================================
# Pipeline Debug Endpoints (n8n-style testing)
# =============================================================================


@simulation_bp.route("/<name>/pipeline")
def view_pipeline(name: str):
    """View pipeline configuration and debug interface."""
    sim = get_simulation(name)
    if not sim:
        flash(f"Simulation '{name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    pipeline_config = sim.getPipelineConfig()

    # Get turn state for player/CPU turn UI
    turn_state = _get_turn_state(sim)

    return render_template(
        "simulations/pipeline.html",
        sim_name=name,
        pipeline=pipeline_config.toDict(),
        pipeline_json=json.dumps(pipeline_config.toDict(), indent=2),
        current_actor=turn_state["currentActor"],
        is_player_turn=turn_state["isPlayerTurn"],
    )


@simulation_bp.route("/<name>/pipeline/config", methods=["GET"])
def get_pipeline_config(name: str):
    """Get pipeline configuration as JSON."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    return sim.getPipelineConfig().toDict()


@simulation_bp.route("/<name>/pipeline/config", methods=["POST"])
def update_pipeline_config(name: str):
    """Update pipeline configuration."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    try:
        from pm6.core.types import PipelineConfig
        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400

        pipeline_config = PipelineConfig.fromDict(data)
        sim.setPipelineConfig(pipeline_config)
        return {"success": True, "config": pipeline_config.toDict()}
    except Exception as e:
        return {"error": str(e)}, 400


@simulation_bp.route("/<name>/pipeline/preview/<int:step_index>")
def preview_pipeline_step(name: str, step_index: int):
    """Preview what a pipeline step would receive as input."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)
        preview = executor.getStepPreview(step_index)
        return {"stepIndex": step_index, "inputs": preview}
    except Exception as e:
        return {"error": str(e)}, 500


@simulation_bp.route("/<name>/pipeline/step", methods=["POST"])
def execute_pipeline_step(name: str):
    """Execute a single pipeline step."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        data = request.get_json() or {}
        step_index = data.get("stepIndex", 0)
        dry_run = data.get("dryRun", False)

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)

        if dry_run:
            executor.setDryRunMode(True)

        result = executor.executeStep(step_index)
        result_dict = result.toDict()

        # Save to logs
        run_type = f"step{step_index}_dry" if dry_run else f"step{step_index}"
        _save_pipeline_log(name, result_dict, run_type)

        return result_dict
    except Exception as e:
        return {"error": str(e)}, 500


@simulation_bp.route("/<name>/pipeline/execute", methods=["POST"])
def execute_pipeline_all(name: str):
    """Execute all pipeline steps for a complete turn."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    # Debug info
    debug_info = {
        "isTestMode": sim.isTestMode,
        "isCacheEnabled": sim.isCacheEnabled,
        "llmClientType": type(sim._llmClient).__name__,
    }

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        data = request.get_json() or {}
        dry_run = data.get("dryRun", False)

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)

        if dry_run:
            result = executor.dryRun()
        else:
            result = executor.executeAll()

        result_dict = result.toDict()
        result_dict["_debug"] = debug_info  # Include debug info

        # Save to logs
        run_type = "execute_dry" if dry_run else "execute"
        _save_pipeline_log(name, result_dict, run_type)

        return result_dict
    except Exception as e:
        return {"error": str(e), "_debug": debug_info}, 500


@simulation_bp.route("/<name>/pipeline/dry-run", methods=["POST"])
def dry_run_pipeline(name: str):
    """Dry run the entire pipeline without LLM calls."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)
        result = executor.dryRun()
        result_dict = result.toDict()

        # Save to logs
        _save_pipeline_log(name, result_dict, "dry-run")

        return result_dict
    except Exception as e:
        return {"error": str(e)}, 500


# =============================================================================
# Turn Management Endpoints (Player vs CPU)
# =============================================================================


def _get_turn_state(sim) -> dict:
    """Get current turn state - who's turn it is and if they're player-controlled."""
    world_state = sim.getWorldState()

    # Check for explicit player pending flag (set by play endpoint)
    if world_state.get("_playerPending"):
        current_actor = world_state.get("currentActor", "player")
        return {
            "currentActor": current_actor,
            "isPlayerTurn": True,
        }

    # Try to determine current actor from world state
    current_actor = world_state.get("currentActor") or world_state.get("currentPlayer")
    if not current_actor:
        # Check for turn index
        turn_index = world_state.get("turnIndex", 0)
        actors = world_state.get("actors", [])
        if actors and turn_index < len(actors):
            current_actor = actors[turn_index]

    # Determine if current actor is player-controlled
    is_player_turn = False
    if current_actor:
        # Check agents for controlledBy
        agent_names = sim.listAgents()
        if current_actor in agent_names:
            try:
                agent = sim.getAgent(current_actor)
                is_player_turn = getattr(agent, "controlledBy", "cpu") == "player"
            except Exception:
                pass

    return {
        "currentActor": current_actor or "Unknown",
        "isPlayerTurn": is_player_turn,
    }


@simulation_bp.route("/<name>/pipeline/turn-state")
def get_turn_state(name: str):
    """Get current turn state - who's turn and if player-controlled."""
    sim = get_simulation(name)
    if not sim:
        return {"success": False, "error": f"Simulation '{name}' not found"}, 404

    turn_state = _get_turn_state(sim)
    return {
        "success": True,
        "currentActor": turn_state["currentActor"],
        "isPlayerTurn": turn_state["isPlayerTurn"],
    }


@simulation_bp.route("/<name>/pipeline/execute-cpu-turn", methods=["POST"])
def execute_cpu_turn(name: str):
    """Execute a single CPU turn (for CPU-controlled actors only)."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    turn_state = _get_turn_state(sim)
    if turn_state["isPlayerTurn"]:
        return {
            "success": False,
            "error": "It's the player's turn. Use the action buttons instead.",
            "currentActor": turn_state["currentActor"],
        }

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)
        result = executor.executeAll()
        result_dict = result.toDict()

        # Save to logs
        _save_pipeline_log(name, result_dict, "cpu-turn")

        # Get updated turn state
        new_turn_state = _get_turn_state(sim)

        return {
            "success": True,
            "result": result_dict,
            "previousActor": turn_state["currentActor"],
            "currentActor": new_turn_state["currentActor"],
            "isPlayerTurn": new_turn_state["isPlayerTurn"],
        }
    except Exception as e:
        return {"error": str(e)}, 500


@simulation_bp.route("/<name>/pipeline/auto-advance", methods=["POST"])
def auto_advance_to_player(name: str):
    """Execute CPU turns until it's a player's turn."""
    sim = get_simulation(name)
    if not sim:
        return {"error": f"Simulation '{name}' not found"}, 404

    max_turns = 20  # Safety limit
    turns_executed = []

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
        executor = PipelineExecutor(engine)

        for i in range(max_turns):
            turn_state = _get_turn_state(sim)

            # Stop if it's player's turn
            if turn_state["isPlayerTurn"]:
                return {
                    "success": True,
                    "message": f"Stopped at player turn after {len(turns_executed)} CPU turns",
                    "turnsExecuted": turns_executed,
                    "currentActor": turn_state["currentActor"],
                    "isPlayerTurn": True,
                }

            # Execute CPU turn
            result = executor.executeAll()
            turns_executed.append({
                "actor": turn_state["currentActor"],
                "turn": i + 1,
                "result": result.toDict(),
            })

            # Recreate engine for next turn (in case state changed)
            engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
            executor = PipelineExecutor(engine)

        # Hit max turns
        final_state = _get_turn_state(sim)
        return {
            "success": False,
            "message": f"Reached max turns ({max_turns}) without player turn",
            "turnsExecuted": turns_executed,
            "currentActor": final_state["currentActor"],
            "isPlayerTurn": final_state["isPlayerTurn"],
        }

    except Exception as e:
        return {"error": str(e), "turnsExecuted": turns_executed}, 500


def _extract_state_changes(old_state: dict, new_state: dict) -> list:
    """Extract meaningful changes between two world states for narration."""
    changes = []

    def compare_dicts(old: dict, new: dict, prefix: str = ""):
        for key, new_val in new.items():
            old_val = old.get(key)
            full_key = f"{prefix}{key}" if prefix else key

            # Skip internal keys
            if key.startswith("_"):
                continue

            if old_val is None and new_val is not None:
                changes.append({"type": "info", "text": f"{full_key}: {new_val}"})
            elif isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                if new_val != old_val:
                    diff = new_val - old_val
                    change_type = "increase" if diff > 0 else "decrease"
                    changes.append({
                        "type": change_type,
                        "text": f"{full_key}: {old_val} → {new_val} ({'+' if diff > 0 else ''}{diff})"
                    })
            elif new_val != old_val:
                if not isinstance(new_val, dict):
                    changes.append({"type": "info", "text": f"{full_key}: {new_val}"})

    compare_dicts(old_state, new_state)
    return changes[:10]  # Limit to 10 changes


def _generate_narration(actor: str, result: dict, changes: list) -> str:
    """Generate narration text from pipeline execution result."""
    # Try to extract narration from execute_agents step outputs
    for step in result.get("steps", []):
        if step.get("stepName") == "execute_agents":
            actions = step.get("outputs", {}).get("actions", [])
            for action in actions:
                content = action.get("content", "")
                if content and len(content) > 10:
                    return content  # Return full narration

    # Legacy: Try stepResults format
    if result.get("stepResults"):
        for step_result in result["stepResults"]:
            if step_result.get("response"):
                response = step_result["response"]
                if isinstance(response, str) and len(response) > 10:
                    return response  # Return full response

    # Fallback narration based on changes
    if changes:
        change_texts = [c["text"] for c in changes[:3]]
        return f"{actor} takes action. {', '.join(change_texts)}."

    return f"{actor} completes their turn."


def _advance_turn(sim) -> None:
    """Advance to the next actor in the turn order."""
    world_state = sim.getWorldState()
    actors = world_state.get("actors", [])

    if not actors:
        return  # No actors to advance

    current_actor = world_state.get("currentActor")
    turn_index = world_state.get("turnIndex", 0)

    # Find next actor
    if current_actor and current_actor in actors:
        current_index = actors.index(current_actor)
        next_index = (current_index + 1) % len(actors)
    else:
        next_index = (turn_index + 1) % len(actors)

    # Update world state
    world_state["turnIndex"] = next_index
    world_state["currentActor"] = actors[next_index]
    sim.setWorldState(world_state)


@simulation_bp.route("/<name>/pipeline/play", methods=["POST"])
def play_until_player_turn(name: str):
    """Execute simulation until a player turn is reached.

    Returns narration and state changes for each turn executed.
    """
    sim = get_simulation(name)
    if not sim:
        return {"success": False, "error": f"Simulation '{name}' not found"}, 404

    max_turns = 20  # Safety limit
    turns = []

    try:
        from pm6.core.engine import SimulationEngine
        from pm6.core.pipeline_executor import PipelineExecutor

        # Check if already player's turn
        initial_state = _get_turn_state(sim)
        if initial_state["isPlayerTurn"]:
            return {
                "success": True,
                "turns": [],
                "currentActor": initial_state["currentActor"],
                "isPlayerTurn": True,
                "message": "Already player's turn"
            }

        # Check if any player agents exist
        agent_names = sim.listAgents()
        has_player_agent = False
        for name_check in agent_names:
            try:
                agent = sim.getAgent(name_check)
                if getattr(agent, "controlledBy", "cpu") == "player":
                    has_player_agent = True
                    break
            except Exception:
                pass

        if not has_player_agent:
            return {
                "success": False,
                "turns": [],
                "currentActor": initial_state["currentActor"],
                "isPlayerTurn": False,
                "error": "No player-controlled agents found. Add an agent with controlledBy='player'."
            }

        for i in range(max_turns):
            turn_state = _get_turn_state(sim)

            # Stop if it's player's turn (from world state)
            if turn_state["isPlayerTurn"]:
                return {
                    "success": True,
                    "turns": turns,
                    "currentActor": turn_state["currentActor"],
                    "isPlayerTurn": True,
                    "message": f"Player turn reached after {len(turns)} CPU turns"
                }

            # Capture state before execution
            state_before = sim.getWorldState().copy()

            # Execute the turn
            engine = SimulationEngine(sim, pipelineConfig=sim.getPipelineConfig())
            executor = PipelineExecutor(engine)
            result = executor.executeAll()
            result_dict = result.toDict()

            # Capture state after execution
            state_after = sim.getWorldState()

            # Extract changes and generate narration
            changes = _extract_state_changes(state_before, state_after)

            # Check if player turn is pending by looking at step outputs
            player_pending = False
            player_agent = None
            executed_agent = None
            for step in result_dict.get("steps", []):
                step_name = step.get("stepName")
                outputs = step.get("outputs", {})

                if step_name == "execute_agents":
                    # Get the actual agent that executed
                    actions = outputs.get("actions", [])
                    if actions:
                        executed_agent = actions[0].get("agentName")

                if step_name == "player_turn":
                    player_pending = outputs.get("playerPending", False)
                    player_agent = outputs.get("playerAgent")

            # Use the actual executed agent name, or fall back to turn state
            actor_name = executed_agent or turn_state["currentActor"]
            narration = _generate_narration(actor_name, result_dict, changes)

            turns.append({
                "turn": i + 1,
                "actor": actor_name,
                "isPlayer": False,
                "narration": narration,
                "changes": changes,
                "result": result_dict
            })

            # Save to logs
            _save_pipeline_log(name, result_dict, f"play-turn-{i+1}")

            # CRITICAL: Check if pipeline says it's player's turn
            if player_pending:
                # Update world state so turn-state endpoint returns correct info
                world_state = sim.getWorldState()
                world_state["currentActor"] = player_agent or "player"
                world_state["_playerPending"] = True
                sim.setWorldState(world_state)

                return {
                    "success": True,
                    "turns": turns,
                    "currentActor": player_agent or "player",
                    "isPlayerTurn": True,
                    "message": f"Player turn reached after {len(turns)} turn(s)"
                }

            # Only advance turn if NOT waiting for player
            _advance_turn(sim)

        # Hit max turns without reaching player
        final_state = _get_turn_state(sim)
        return {
            "success": True,
            "turns": turns,
            "currentActor": final_state["currentActor"],
            "isPlayerTurn": final_state["isPlayerTurn"],
            "message": f"Executed {max_turns} turns (max reached)"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "turns": turns,
            "currentActor": _get_turn_state(sim).get("currentActor", "Unknown"),
            "isPlayerTurn": False
        }, 500
