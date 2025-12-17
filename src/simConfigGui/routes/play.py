"""Play Mode routes for end-player experience."""

import json
import logging
from flask import Blueprint, current_app, jsonify, render_template, request

from pm6.core.engine import SimulationEngine
from pm6.core.types import ResponseFormatConfig, ResponseFormatType

logger = logging.getLogger("simConfigGui.routes.play")

play_bp = Blueprint("play", __name__)


def _get_or_create_engine(sim_name: str) -> SimulationEngine | None:
    """Get or create an engine for the simulation.

    Bootstraps Play Mode with:
    - Initial world state (from state/initial.json)
    - Initial event (from events/initial.json)

    Args:
        sim_name: Simulation name.

    Returns:
        SimulationEngine instance or None if sim not found.
    """
    if sim_name not in current_app.simulations:
        return None

    sim = current_app.simulations[sim_name]

    # Check if engine exists in app storage
    if not hasattr(current_app, "engines"):
        current_app.engines = {}

    if sim_name not in current_app.engines:
        # Bootstrap: Load initial world state if available
        initialState = sim.loadInitialWorldState()
        if initialState:
            sim.setWorldState(initialState)
            logger.info(f"Loaded initial world state for {sim_name}")

        # Create engine and enable Play Mode (auto-bootstraps initial event)
        engine = SimulationEngine(sim)
        engine.enablePlayMode(autoBootstrap=True)

        current_app.engines[sim_name] = engine
        logger.info(f"Created Play Mode engine for {sim_name}")

    return current_app.engines[sim_name]


@play_bp.route("/play/<sim_name>")
def play_view(sim_name: str):
    """Render the Play Mode view for a simulation.

    Args:
        sim_name: Simulation name.
    """
    if sim_name not in current_app.simulations:
        return render_template(
            "play/error.html",
            error="Simulation not found",
            sim_name=sim_name,
        ), 404

    sim = current_app.simulations[sim_name]
    engine = _get_or_create_engine(sim_name)

    # Get initial state
    world_state = sim.getWorldState()
    agents = sim.listAgents()  # Returns list of agent names (strings)

    return render_template(
        "play/view.html",
        sim_name=sim_name,
        world_state=world_state,
        agents=agents,
        turn_number=engine.currentTurn if engine else 0,
    )


@play_bp.route("/play/<sim_name>/step", methods=["POST"])
def step_turn(sim_name: str):
    """Execute a turn in Play Mode.

    Returns:
        JSON with PlayModeOutput data.
    """
    engine = _get_or_create_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        # Get optional format config from request
        format_type = request.json.get("format_type") if request.json else None
        format_config = None

        if format_type:
            format_config = ResponseFormatConfig(
                formatType=ResponseFormatType(format_type),
                choiceCount=request.json.get("choice_count", 4),
                showImpacts=request.json.get("show_impacts", True),
            )

        # Execute turn
        output = engine.stepPlayMode(formatConfig=format_config)

        return jsonify({
            "success": True,
            "output": output.toDict(),
        })

    except Exception as e:
        logger.error(f"Error in step_turn: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/choice", methods=["POST"])
def submit_choice(sim_name: str):
    """Submit a player choice selection.

    Expects JSON: {"choice_id": "A"}

    Returns:
        JSON with updated world state.
    """
    engine = _get_or_create_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "choice_id" not in data:
        return jsonify({"error": "Missing choice_id"}), 400

    try:
        choice_id = data["choice_id"]
        new_state = engine.submitPlayerChoice(choice_id)

        return jsonify({
            "success": True,
            "world_state": new_state,
            "choice_applied": choice_id,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting choice: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/free-text", methods=["POST"])
def submit_free_text(sim_name: str):
    """Submit free-form text input.

    Expects JSON: {"text": "player's input"}

    Returns:
        JSON with new PlayModeOutput after interpretation.
    """
    engine = _get_or_create_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "text" not in data:
        return jsonify({"error": "Missing text"}), 400

    try:
        text = data["text"]
        output = engine.submitFreeText(text)

        return jsonify({
            "success": True,
            "output": output.toDict(),
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting free text: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/state")
def get_state(sim_name: str):
    """Get current game state.

    Returns:
        JSON with world state, turn number, and pending choices.
    """
    engine = _get_or_create_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    sim = current_app.simulations[sim_name]

    return jsonify({
        "world_state": sim.getWorldState(),
        "turn_number": engine.currentTurn,
        "has_pending_choices": engine.hasPendingChoices(),
        "pending_choices": [c.toDict() for c in engine.getPendingChoices()],
        "last_output": engine.lastPlayModeOutput.toDict() if engine.lastPlayModeOutput else None,
    })


@play_bp.route("/play/<sim_name>/reset", methods=["POST"])
def reset_play(sim_name: str):
    """Reset the Play Mode session.

    Reloads initial world state and re-schedules initial event.

    Returns:
        JSON with success status.
    """
    if sim_name not in current_app.simulations:
        return jsonify({"error": "Simulation not found"}), 404

    sim = current_app.simulations[sim_name]

    try:
        # Reload initial world state
        initialState = sim.loadInitialWorldState()
        if initialState:
            sim.setWorldState(initialState)
            logger.info(f"Reloaded initial world state for {sim_name}")

        # Get or create engine
        engine = _get_or_create_engine(sim_name)
        if engine is None:
            return jsonify({"error": "Failed to create engine"}), 500

        # Reset engine and re-enable play mode (re-bootstraps initial event)
        engine.reset()
        engine.enablePlayMode(autoBootstrap=True)

        return jsonify({
            "success": True,
            "turn_number": 0,
            "world_state": sim.getWorldState(),
        })

    except Exception as e:
        logger.error(f"Error resetting play mode: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Chief of Staff Mode Routes
# =============================================================================


def _get_or_create_cos_engine(sim_name: str) -> SimulationEngine | None:
    """Get or create an engine with CoS mode enabled.

    Args:
        sim_name: Simulation name.

    Returns:
        SimulationEngine with CoS mode or None if sim not found.
    """
    if sim_name not in current_app.simulations:
        return None

    sim = current_app.simulations[sim_name]

    # Check if engine exists in app storage
    if not hasattr(current_app, "engines"):
        current_app.engines = {}

    if sim_name not in current_app.engines:
        # Bootstrap: Load initial world state if available
        initialState = sim.loadInitialWorldState()
        if initialState:
            sim.setWorldState(initialState)
            logger.info(f"Loaded initial world state for {sim_name}")

        # Create engine with both Play Mode and CoS Mode
        engine = SimulationEngine(sim)
        engine.enablePlayMode(autoBootstrap=True)
        engine.enableCosMode()

        current_app.engines[sim_name] = engine
        logger.info(f"Created CoS Mode engine for {sim_name}")

    # Ensure CoS mode is enabled
    engine = current_app.engines[sim_name]
    if not engine.isCosModeEnabled:
        engine.enableCosMode()

    return engine


@play_bp.route("/play/<sim_name>/cos")
def cos_view(sim_name: str):
    """Render the Chief of Staff Mode view for a simulation.

    Args:
        sim_name: Simulation name.
    """
    if sim_name not in current_app.simulations:
        return render_template(
            "play/error.html",
            error="Simulation not found",
            sim_name=sim_name,
        ), 404

    sim = current_app.simulations[sim_name]
    engine = _get_or_create_cos_engine(sim_name)

    # Get initial state
    world_state = sim.getWorldState()
    meetable_agents = engine.cosGetMeetableAgents() if engine else []

    return render_template(
        "play/cos_view.html",
        sim_name=sim_name,
        world_state=world_state,
        meetable_agents=meetable_agents,
        turn_number=engine.currentTurn if engine else 0,
    )


@play_bp.route("/play/<sim_name>/cos/step", methods=["POST"])
def cos_step_turn(sim_name: str):
    """Execute a turn in CoS Mode.

    Returns:
        JSON with CosBriefingOutput data.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        # Execute turn and get briefing
        briefing = engine.stepCosMode()

        return jsonify({
            "success": True,
            "briefing": briefing.toDict(),
            "phase": engine.cosPhase.value if engine.cosPhase else "unknown",
        })

    except Exception as e:
        logger.error(f"Error in cos_step_turn: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/meeting/start", methods=["POST"])
def cos_start_meeting(sim_name: str):
    """Start a meeting with an agent.

    Expects JSON: {"agent_name": "mossad_director"}

    Returns:
        JSON with meeting state.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "agent_name" not in data:
        return jsonify({"error": "Missing agent_name"}), 400

    try:
        agent_name = data["agent_name"]
        meeting = engine.cosStartMeeting(agent_name)

        if meeting is None:
            return jsonify({"error": f"Agent {agent_name} is not available for meeting"}), 400

        return jsonify({
            "success": True,
            "meeting": meeting.toDict(),
            "phase": "meeting",
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error starting meeting: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/meeting/message", methods=["POST"])
def cos_send_message(sim_name: str):
    """Send a message in the current meeting.

    Expects JSON: {"message": "What is your assessment?"}

    Returns:
        JSON with agent's response.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Missing message"}), 400

    try:
        message = data["message"]
        response = engine.cosSendMessage(message)

        if response is None:
            return jsonify({"error": "Not in a meeting"}), 400

        meeting = engine.cosGetCurrentMeeting()

        return jsonify({
            "success": True,
            "response": response,
            "meeting": meeting.toDict() if meeting else None,
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/meeting/end", methods=["POST"])
def cos_end_meeting(sim_name: str):
    """End the current meeting and return to briefing.

    Returns:
        JSON with updated briefing.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        briefing = engine.cosEndMeeting()

        if briefing is None:
            return jsonify({"error": "Not in a meeting"}), 400

        sim = current_app.simulations[sim_name]

        return jsonify({
            "success": True,
            "briefing": briefing.toDict(),
            "phase": engine.cosPhase.value if engine.cosPhase else "briefing",
            "world_state": sim.getWorldState(),
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error ending meeting: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/decide", methods=["POST"])
def cos_proceed_to_decision(sim_name: str):
    """Proceed from briefing to decision phase.

    Returns:
        JSON with briefing in decision phase.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        briefing = engine.cosProceedToDecision()

        if briefing is None:
            return jsonify({"error": "Failed to proceed to decision"}), 400

        return jsonify({
            "success": True,
            "briefing": briefing.toDict(),
            "phase": "decision",
        })

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error proceeding to decision: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/decision", methods=["POST"])
def cos_submit_decision(sim_name: str):
    """Submit a strategic decision.

    Expects JSON: {"choice_id": "A"}

    Returns:
        JSON with updated world state.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "choice_id" not in data:
        return jsonify({"error": "Missing choice_id"}), 400

    try:
        choice_id = data["choice_id"]
        new_state = engine.cosSubmitDecision(choice_id)

        return jsonify({
            "success": True,
            "world_state": new_state,
            "choice_applied": choice_id,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error submitting decision: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/agents")
def cos_get_agents(sim_name: str):
    """Get list of meetable agents.

    Returns:
        JSON with list of agents available for meeting.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    agents = engine.cosGetMeetableAgents()

    return jsonify({
        "success": True,
        "agents": agents,
    })


@play_bp.route("/play/<sim_name>/cos/state")
def cos_get_state(sim_name: str):
    """Get current CoS game state.

    Returns:
        JSON with full CoS state including phase and meeting info.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    sim = current_app.simulations[sim_name]
    cos_state = engine.cosPlayState

    return jsonify({
        "world_state": sim.getWorldState(),
        "turn_number": engine.currentTurn,
        "phase": engine.cosPhase.value if engine.cosPhase else "unknown",
        "cos_state": cos_state.toDict() if cos_state else None,
        "meetable_agents": engine.cosGetMeetableAgents(),
        "pending_choices": [c.toDict() for c in engine.getPendingChoices()],
    })


@play_bp.route("/play/<sim_name>/cos/reset", methods=["POST"])
def cos_reset(sim_name: str):
    """Reset the CoS Mode session.

    Returns:
        JSON with success status.
    """
    if sim_name not in current_app.simulations:
        return jsonify({"error": "Simulation not found"}), 404

    sim = current_app.simulations[sim_name]

    try:
        # Reload initial world state
        initialState = sim.loadInitialWorldState()
        if initialState:
            sim.setWorldState(initialState)
            logger.info(f"Reloaded initial world state for {sim_name}")

        # Get or create engine
        engine = _get_or_create_cos_engine(sim_name)
        if engine is None:
            return jsonify({"error": "Failed to create engine"}), 500

        # Reset engine and re-enable modes
        engine.reset()
        engine.enablePlayMode(autoBootstrap=True)
        engine.enableCosMode()

        return jsonify({
            "success": True,
            "turn_number": 0,
            "world_state": sim.getWorldState(),
            "phase": "briefing",
        })

    except Exception as e:
        logger.error(f"Error resetting CoS mode: {e}")
        return jsonify({"error": str(e)}), 500
