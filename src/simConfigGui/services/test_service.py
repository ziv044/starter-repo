"""Service layer for test execution."""

from typing import Any

from simConfigGui.services.simulation_service import get_simulation


def run_interaction(
    sim_name: str,
    agent_name: str,
    user_input: str,
    mock_response: str | None = None,
    force_live: bool = False,
) -> dict[str, Any] | None:
    """Run a single interaction test.

    Args:
        sim_name: Name of the simulation
        agent_name: Name of the agent to interact with
        user_input: The user's input message
        mock_response: Optional mock response (only used in test mode)
        force_live: If True, temporarily disable test mode for this interaction
    """
    sim = get_simulation(sim_name)
    if not sim:
        return None

    # If forcing live mode, temporarily switch off test mode
    original_test_mode = sim.isTestMode
    if force_live and sim.isTestMode:
        sim._testMode = False

    try:
        # Set mock response if provided and in test mode
        if mock_response and sim.isTestMode and sim.mockClient:
            sim.mockClient.addResponse(mock_response)

        response = sim.interact(agent_name, user_input)
        return {
            "success": True,
            "agentName": response.agentName,
            "content": response.content,
            "fromCache": response.fromCache,
            "model": response.model,
            "wasLive": force_live or not original_test_mode,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        # Restore original test mode
        if force_live:
            sim._testMode = original_test_mode


def get_mock_call_history(sim_name: str) -> list[dict[str, Any]]:
    """Get mock call history for a simulation."""
    sim = get_simulation(sim_name)
    if not sim or not sim.isTestMode or not sim.mockClient:
        return []

    return sim.getMockCallHistory()


def reset_mock_state(sim_name: str) -> bool:
    """Reset mock state for a simulation."""
    sim = get_simulation(sim_name)
    if not sim or not sim.isTestMode or not sim.mockClient:
        return False

    sim.resetMockState()
    return True


def get_interaction_history(sim_name: str) -> list[dict[str, Any]]:
    """Get interaction history for a simulation."""
    sim = get_simulation(sim_name)
    if not sim:
        return []

    return [h.toDict() for h in sim.getHistory()]
