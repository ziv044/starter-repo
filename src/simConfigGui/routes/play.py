"""Play Mode routes for end-player experience.

Includes Document Theater UX with CoS Briefing Generator.
"""

import json
import logging
from flask import Blueprint, current_app, jsonify, render_template, request

from pm6.core.engine import SimulationEngine
from pm6.core.types import ResponseFormatConfig, ResponseFormatType
from pm6.core.agent_prompts import get_enhanced_prompt

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
        JSON with PlayModeOutput data and parsed action items.
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

        # Parse agent responses through CosParser to extract structured action items
        action_items = []
        try:
            from pm6.core.cos_parser import CosParser

            manager = _get_action_items_manager(sim_name)
            parser = CosParser()

            # Parse each agent response
            for agent_action in output.agentResponses:
                agent_name = agent_action.agentName
                response_text = agent_action.content

                if response_text:
                    # Get agent role from simulation if available
                    sim = current_app.simulations[sim_name]
                    agent_config = sim.getAgentConfig(agent_name)
                    agent_role = agent_config.get("role", "") if agent_config else ""

                    # Parse agent response into structured action items
                    parsed_items = parser.parse_response(
                        agent_name=agent_name,
                        agent_role=agent_role,
                        response=response_text,
                        use_llm=False  # Rule-based extraction
                    )

                    # Add parsed items to manager
                    for item in parsed_items:
                        manager.add_item(item)
                        action_items.append(item.to_dict())

            logger.info(f"Play Mode: Parsed {len(action_items)} action items from {len(output.agentResponses)} agent responses")

        except Exception as parse_error:
            logger.warning(f"Failed to parse action items in Play Mode: {parse_error}")
            # Continue without action items - don't block the output

        return jsonify({
            "success": True,
            "output": output.toDict(),
            "action_items": action_items,
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
    """Execute a turn in CoS Mode with Document Theater UX.

    Returns:
        JSON with CosBriefingOutput data, parsed action items, and CoS briefing.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        sim = current_app.simulations[sim_name]

        # Execute turn and get briefing
        briefing = engine.stepCosMode()

        # Parse agent briefs through CosParser to extract structured action items
        action_items = []
        action_items_list = []
        agent_outputs = []

        try:
            from pm6.core.cos_parser import CosParser

            manager = _get_action_items_manager(sim_name)
            parser = CosParser()

            # Parse each agent brief
            for agent_brief in briefing.agentBriefs:
                agent_name = agent_brief.agentName
                agent_role = agent_brief.agentRole
                response_text = agent_brief.fullResponse or agent_brief.summary

                # Collect agent outputs for briefing generation
                agent_outputs.append({
                    "agentName": agent_name,
                    "agentRole": agent_role,
                    "content": response_text,
                })

                if response_text:
                    # Parse agent response into structured action items
                    # Uses improved rule-based extraction with structured block support
                    parsed_items = parser.parse_response(
                        agent_name=agent_name,
                        agent_role=agent_role,
                        response=response_text,
                        use_llm=False
                    )

                    # Add parsed items to manager
                    for item in parsed_items:
                        manager.add_item(item)
                        action_items.append(item.to_dict())
                        action_items_list.append(item)

            logger.info(f"Parsed {len(action_items)} action items from {len(briefing.agentBriefs)} agent briefs")

        except Exception as parse_error:
            logger.warning(f"Failed to parse action items: {parse_error}")
            import traceback
            traceback.print_exc()

        # Generate CoS Briefing for Document Theater UX
        cos_briefing_data = None
        try:
            from pm6.core.cos_briefing import CosBriefingGenerator

            generator = CosBriefingGenerator()
            world_state = sim.getWorldState()

            cos_briefing = generator.generate_briefing(
                turn_number=engine.currentTurn,
                game_time=world_state.get("turn_date", "Unknown"),
                hours_elapsed=engine.currentTurn * 8,  # ~8 hours per turn
                agent_outputs=agent_outputs,
                action_items=action_items_list,
                world_state=world_state,
            )

            cos_briefing_data = cos_briefing.to_dict()
            logger.info(f"Generated CoS briefing with {len(cos_briefing.priority_queue)} priority items")

        except Exception as briefing_error:
            logger.warning(f"Failed to generate CoS briefing: {briefing_error}")
            import traceback
            traceback.print_exc()

        # Get active operations
        operations = []
        try:
            tracker = _get_operations_tracker(sim_name)
            operations = [op.to_dict() for op in tracker.get_active_operations()]
        except Exception:
            pass

        return jsonify({
            "success": True,
            "briefing": briefing.toDict(),
            "phase": engine.cosPhase.value if engine.cosPhase else "unknown",
            "action_items": action_items,
            "cos_briefing": cos_briefing_data,
            "active_operations": operations,
            "world_state": sim.getWorldState(),
        })

    except Exception as e:
        logger.error(f"Error in cos_step_turn: {e}")
        import traceback
        traceback.print_exc()
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

        # Parse action items from agent response
        action_items = []
        if response and meeting:
            try:
                from pm6.core.cos_parser import CosParser
                manager = _get_action_items_manager(sim_name)
                parser = CosParser()

                agent_name = meeting.agentName
                agent_role = meeting.agentRole

                parsed_items = parser.parse_response(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    response=response,
                    use_llm=False
                )
                for item in parsed_items:
                    manager.add_item(item)
                    action_items.append(item.to_dict())

            except Exception as parse_error:
                logger.warning(f"Failed to parse action items from meeting: {parse_error}")

        return jsonify({
            "success": True,
            "response": response,
            "meeting": meeting.toDict() if meeting else None,
            "action_items": action_items,
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


# =============================================================================
# Action Items API Routes
# =============================================================================


def _get_action_items_manager(sim_name: str):
    """Get or create an ActionItemsManager for the simulation.

    Args:
        sim_name: Simulation name.

    Returns:
        ActionItemsManager instance or None if sim not found.
    """
    if not hasattr(current_app, "action_managers"):
        current_app.action_managers = {}

    if sim_name not in current_app.action_managers:
        from pm6.core.cos_parser import ActionItemsManager
        current_app.action_managers[sim_name] = ActionItemsManager()
        logger.info(f"Created ActionItemsManager for {sim_name}")

    return current_app.action_managers[sim_name]


def _get_operations_tracker(sim_name: str):
    """Get or create an OperationsTracker for the simulation.

    Args:
        sim_name: Simulation name.

    Returns:
        OperationsTracker instance or None if sim not found.
    """
    if not hasattr(current_app, "operations_trackers"):
        current_app.operations_trackers = {}

    if sim_name not in current_app.operations_trackers:
        from pm6.core.operations_tracker import OperationsTracker
        current_app.operations_trackers[sim_name] = OperationsTracker()
        logger.info(f"Created OperationsTracker for {sim_name}")

    return current_app.operations_trackers[sim_name]


@play_bp.route("/play/<sim_name>/cos/action-item/approval", methods=["POST"])
def cos_handle_approval(sim_name: str):
    """Handle approval/denial of an action item.

    Expects JSON: {"item_id": "abc123", "approved": true}

    Returns:
        JSON with updated world state.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data or "approved" not in data:
        return jsonify({"error": "Missing item_id or approved"}), 400

    try:
        item_id = data["item_id"]
        approved = data["approved"]

        manager = _get_action_items_manager(sim_name)
        sim = current_app.simulations[sim_name]

        # Get impacts for the approval decision
        impacts = manager.get_impacts_for_approval(item_id, approved)

        # Apply impacts to world state
        world_state = sim.getWorldState()
        for key, value in impacts.items():
            if key in world_state and isinstance(world_state[key], (int, float)):
                world_state[key] = world_state[key] + value
            elif key not in world_state:
                world_state[key] = value
        sim.setWorldState(world_state)

        # Resolve the item
        from pm6.core.action_items import ActionItemStatus
        new_status = ActionItemStatus.APPROVED if approved else ActionItemStatus.DENIED
        manager.resolve_item(item_id, new_status)

        return jsonify({
            "success": True,
            "world_state": sim.getWorldState(),
            "impacts_applied": impacts,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error handling approval: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/authorize-operation", methods=["POST"])
def cos_authorize_operation(sim_name: str):
    """Authorize an operation to begin execution.

    Expects JSON: {"item_id": "abc123"}

    Returns:
        JSON with updated action items.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data:
        return jsonify({"error": "Missing item_id"}), 400

    try:
        item_id = data["item_id"]

        manager = _get_action_items_manager(sim_name)
        tracker = _get_operations_tracker(sim_name)

        # Get the item
        item = manager.get_item(item_id)
        if item is None:
            return jsonify({"error": "Item not found"}), 404

        # Authorize the operation
        operation = tracker.authorize_operation(item, engine.currentTurn)

        # Update the item with the active operation reference
        from pm6.core.action_items import ActionItemStatus
        item.status = ActionItemStatus.IN_PROGRESS
        item.active_operation = operation

        # Get all current action items
        action_items = [i.to_dict() for i in manager.get_pending_items()]

        return jsonify({
            "success": True,
            "operation": operation.to_dict(),
            "action_items": action_items,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error authorizing operation: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/cancel-operation", methods=["POST"])
def cos_cancel_operation(sim_name: str):
    """Cancel/abort an active operation.

    Expects JSON: {"item_id": "abc123"}

    Returns:
        JSON with updated action items.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data:
        return jsonify({"error": "Missing item_id"}), 400

    try:
        item_id = data["item_id"]

        manager = _get_action_items_manager(sim_name)
        tracker = _get_operations_tracker(sim_name)

        # Get the item
        item = manager.get_item(item_id)
        if item is None:
            return jsonify({"error": "Item not found"}), 404

        # Cancel the operation
        if item.active_operation:
            tracker.cancel_operation(item.active_operation.id, "Aborted by player")

        # Update item status
        from pm6.core.action_items import ActionItemStatus
        manager.resolve_item(item_id, ActionItemStatus.CANCELLED)

        # Get all current action items
        action_items = [i.to_dict() for i in manager.get_pending_items()]

        return jsonify({
            "success": True,
            "action_items": action_items,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error cancelling operation: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/demands", methods=["POST"])
def cos_handle_demands(sim_name: str):
    """Handle responses to demand items.

    Expects JSON: {"item_id": "abc123", "responses": {"demand1": "agree", "demand2": "disagree"}}

    Returns:
        JSON with updated world state.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data:
        return jsonify({"error": "Missing item_id"}), 400

    try:
        item_id = data["item_id"]
        responses = data.get("responses", {})

        manager = _get_action_items_manager(sim_name)
        sim = current_app.simulations[sim_name]

        # Get impacts for the demand responses
        impacts = manager.get_impacts_for_demands(item_id, responses)

        # Apply impacts to world state
        world_state = sim.getWorldState()
        for key, value in impacts.items():
            if key in world_state and isinstance(world_state[key], (int, float)):
                world_state[key] = world_state[key] + value
            elif key not in world_state:
                world_state[key] = value
        sim.setWorldState(world_state)

        # Resolve the item
        from pm6.core.action_items import ActionItemStatus
        manager.resolve_item(item_id, ActionItemStatus.RESOLVED)

        return jsonify({
            "success": True,
            "world_state": sim.getWorldState(),
            "impacts_applied": impacts,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error handling demands: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/acknowledge", methods=["POST"])
def cos_acknowledge_info(sim_name: str):
    """Acknowledge an info item (marks as read).

    Expects JSON: {"item_id": "abc123"}

    Returns:
        JSON with success status.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data:
        return jsonify({"error": "Missing item_id"}), 400

    try:
        item_id = data["item_id"]

        manager = _get_action_items_manager(sim_name)

        # Mark as acknowledged
        from pm6.core.action_items import ActionItemStatus
        manager.resolve_item(item_id, ActionItemStatus.ACKNOWLEDGED)

        return jsonify({
            "success": True,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error acknowledging info: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/defer", methods=["POST"])
def cos_defer_item(sim_name: str):
    """Defer an action item to the next turn.

    Expects JSON: {"item_id": "abc123"}

    Returns:
        JSON with success status.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data:
        return jsonify({"error": "Missing item_id"}), 400

    try:
        item_id = data["item_id"]

        manager = _get_action_items_manager(sim_name)

        # Mark as deferred
        from pm6.core.action_items import ActionItemStatus
        item = manager.get_item(item_id)
        if item:
            item.status = ActionItemStatus.DEFERRED

        return jsonify({
            "success": True,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error deferring item: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-item/option", methods=["POST"])
def cos_select_option(sim_name: str):
    """Select an option from an OPTIONS action item.

    Expects JSON: {"item_id": "abc123", "option_id": "0"}

    Returns:
        JSON with success status and updated world state.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    data = request.json
    if not data or "item_id" not in data or "option_id" not in data:
        return jsonify({"error": "Missing item_id or option_id"}), 400

    try:
        item_id = data["item_id"]
        option_id = data["option_id"]

        manager = _get_action_items_manager(sim_name)

        # Get impacts for selected option
        impacts = manager.get_impacts_for_option(item_id, option_id)

        # Apply impacts to world state
        world_state = engine.getWorldState()
        for key, value in impacts.items():
            if key in world_state:
                world_state[key] = world_state.get(key, 0) + value
            else:
                world_state[key] = value
        engine.setWorldState(world_state)

        # Resolve the item
        from pm6.core.action_items import ActionItemStatus
        manager.resolve_item(item_id, ActionItemStatus.RESOLVED)

        return jsonify({
            "success": True,
            "impacts_applied": impacts,
            "world_state": world_state,
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error selecting option: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/action-items")
def cos_get_action_items(sim_name: str):
    """Get all pending action items.

    Returns:
        JSON with list of pending action items.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        manager = _get_action_items_manager(sim_name)
        items = manager.get_pending_items()

        return jsonify({
            "success": True,
            "action_items": [i.to_dict() for i in items],
        })

    except Exception as e:
        logger.error(f"Error getting action items: {e}")
        return jsonify({"error": str(e)}), 500


@play_bp.route("/play/<sim_name>/cos/operations")
def cos_get_operations(sim_name: str):
    """Get all active operations.

    Returns:
        JSON with list of active operations.
    """
    engine = _get_or_create_cos_engine(sim_name)
    if engine is None:
        return jsonify({"error": "Simulation not found"}), 404

    try:
        tracker = _get_operations_tracker(sim_name)
        operations = tracker.get_active_operations()

        return jsonify({
            "success": True,
            "operations": [op.to_dict() for op in operations],
        })

    except Exception as e:
        logger.error(f"Error getting operations: {e}")
        return jsonify({"error": str(e)}), 500
