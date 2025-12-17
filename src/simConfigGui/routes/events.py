"""Event injection routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from simConfigGui.services.event_service import (
    STANDARD_EVENTS,
    get_event_history,
    inject_event,
    parse_event_data,
)
from simConfigGui.services.simulation_service import get_simulation

events_bp = Blueprint("events", __name__)


@events_bp.route("/simulations/<sim_name>/events/")
def events_page(sim_name: str):
    """Event management page."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    history = get_event_history(sim_name, limit=20)
    return render_template(
        "events/inject.html",
        sim_name=sim_name,
        events=history,
        standard_events=STANDARD_EVENTS,
    )


@events_bp.route("/simulations/<sim_name>/events/inject", methods=["POST"])
def inject_event_view(sim_name: str):
    """Inject an event into the simulation."""
    sim = get_simulation(sim_name)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or \
              "application/json" in request.headers.get("Accept", "") or \
              request.content_type == "application/x-www-form-urlencoded"

    if not sim:
        if is_ajax:
            return {"success": False, "error": f"Simulation '{sim_name}' not found"}, 404
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    event_name = request.form.get("eventName", "").strip()
    custom_event_name = request.form.get("customEventName", "").strip()
    event_data_str = request.form.get("eventData", "{}")
    source = request.form.get("source", "admin").strip()

    # Use custom event name if "custom" is selected
    if event_name == "custom" and custom_event_name:
        event_name = custom_event_name
    elif event_name == "custom":
        if is_ajax:
            return {"success": False, "error": "Custom event name is required"}, 400
        flash("Custom event name is required", "error")
        return redirect(url_for("events.events_page", sim_name=sim_name))

    if not event_name:
        if is_ajax:
            return {"success": False, "error": "Event name is required"}, 400
        flash("Event name is required", "error")
        return redirect(url_for("events.events_page", sim_name=sim_name))

    try:
        event_data = parse_event_data(event_data_str)
        result = inject_event(sim_name, event_name, event_data, source)

        if result:
            # Clear player pending flag when player takes action
            if event_name.startswith("player_"):
                world_state = sim.getWorldState()
                if world_state.get("_playerPending"):
                    world_state["_playerPending"] = False
                    # Clear currentActor so play endpoint continues CPU turns
                    world_state["currentActor"] = None
                    sim.setWorldState(world_state)

            if is_ajax:
                return {"success": True, "event": event_name, "message": "Event injected successfully"}
            flash(f"Event '{event_name}' injected successfully", "success")
        else:
            if is_ajax:
                return {"success": False, "error": "Failed to inject event"}, 500
            flash("Failed to inject event", "error")
    except Exception as e:
        if is_ajax:
            return {"success": False, "error": str(e)}, 500
        flash(f"Error injecting event: {e}", "error")

    return redirect(url_for("events.events_page", sim_name=sim_name))


@events_bp.route("/simulations/<sim_name>/events/history")
def event_history(sim_name: str):
    """View event history."""
    sim = get_simulation(sim_name)
    if not sim:
        flash(f"Simulation '{sim_name}' not found", "error")
        return redirect(url_for("simulation.list_simulations_view"))

    limit = request.args.get("limit", 50, type=int)
    history = get_event_history(sim_name, limit=limit)

    return render_template(
        "events/history.html",
        sim_name=sim_name,
        events=history,
    )
