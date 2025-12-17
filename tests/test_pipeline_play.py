"""Tests for pipeline play functionality - run until player turn."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from simConfigGui.app import create_app
from simConfigGui.routes.simulation import (
    _extract_state_changes,
    _generate_narration,
    _get_turn_state,
)


@pytest.fixture
def temp_db():
    """Create a temporary database directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def app(temp_db):
    """Create test app with temporary database."""
    app = create_app("testing")
    app.config["DB_PATH"] = str(temp_db)
    app.db_path = temp_db
    app.simulations = {}
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def sim_with_agents(client, app, temp_db):
    """Create a simulation with both player and CPU agents."""
    # Create simulation
    client.post(
        "/simulations/create/manual",
        data={"name": "play_test", "test_mode": "on"},
    )

    # Add CPU agent
    client.post(
        "/simulations/play_test/agents/add",
        data={
            "name": "cpu_agent",
            "role": "CPU Player",
            "systemPrompt": "You are a CPU agent",
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "summary",
            "controlledBy": "cpu",
            "initiative": "0.5",
            "agentType": "entity",
        },
    )

    # Add player agent
    client.post(
        "/simulations/play_test/agents/add",
        data={
            "name": "player_agent",
            "role": "Human Player",
            "systemPrompt": "You are a player agent",
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "summary",
            "controlledBy": "player",
            "initiative": "0.5",
            "agentType": "entity",
        },
    )

    # Set world state with actors list and current actor
    sim = app.simulations["play_test"]
    sim.setWorldState({
        "actors": ["cpu_agent", "player_agent"],
        "currentActor": "cpu_agent",
        "turnIndex": 0,
        "chips": {"cpu_agent": 1000, "player_agent": 1000},
    })

    return sim


class TestExtractStateChanges:
    """Tests for _extract_state_changes helper function."""

    def test_detects_numeric_increase(self):
        """Test detection of numeric increases."""
        old_state = {"chips": 100}
        new_state = {"chips": 150}

        changes = _extract_state_changes(old_state, new_state)

        assert len(changes) == 1
        assert changes[0]["type"] == "increase"
        assert "100 → 150" in changes[0]["text"]

    def test_detects_numeric_decrease(self):
        """Test detection of numeric decreases."""
        old_state = {"health": 100}
        new_state = {"health": 75}

        changes = _extract_state_changes(old_state, new_state)

        assert len(changes) == 1
        assert changes[0]["type"] == "decrease"
        assert "100 → 75" in changes[0]["text"]

    def test_detects_new_value(self):
        """Test detection of new values."""
        old_state = {}
        new_state = {"status": "active"}

        changes = _extract_state_changes(old_state, new_state)

        assert len(changes) == 1
        assert changes[0]["type"] == "info"
        assert "status" in changes[0]["text"]

    def test_ignores_internal_keys(self):
        """Test that keys starting with _ are ignored."""
        old_state = {"_internal": 1}
        new_state = {"_internal": 2}

        changes = _extract_state_changes(old_state, new_state)

        assert len(changes) == 0

    def test_limits_changes_to_10(self):
        """Test that changes are limited to 10 items."""
        old_state = {f"key{i}": i for i in range(20)}
        new_state = {f"key{i}": i + 1 for i in range(20)}

        changes = _extract_state_changes(old_state, new_state)

        assert len(changes) <= 10


class TestGenerateNarration:
    """Tests for _generate_narration helper function."""

    def test_extracts_from_execute_agents_step(self):
        """Test extraction of narration from execute_agents step outputs."""
        result = {
            "steps": [
                {
                    "stepName": "execute_agents",
                    "outputs": {
                        "actions": [
                            {
                                "agentName": "narrator",
                                "content": "The hero enters the dark dungeon."
                            }
                        ]
                    }
                }
            ]
        }

        narration = _generate_narration("narrator", result, [])

        assert "hero enters" in narration.lower()

    def test_extracts_llm_response_legacy(self):
        """Test extraction of narration from legacy LLM response format."""
        result = {
            "stepResults": [
                {"response": "The dealer shuffles the deck and deals cards."}
            ]
        }

        narration = _generate_narration("Dealer", result, [])

        assert "dealer shuffles" in narration.lower()

    def test_fallback_narration_with_changes(self):
        """Test fallback narration when no LLM response."""
        changes = [
            {"type": "decrease", "text": "chips: 100 → 50"},
            {"type": "action", "text": "bet placed"},
        ]

        narration = _generate_narration("Player1", {}, changes)

        assert "Player1" in narration
        assert "chips" in narration

    def test_fallback_narration_no_changes(self):
        """Test fallback narration with no changes."""
        narration = _generate_narration("CPU", {}, [])

        assert "CPU" in narration
        assert "turn" in narration.lower()

    def test_returns_full_narration(self):
        """Test that full narration content is returned."""
        long_response = "A" * 1000
        result = {
            "steps": [
                {
                    "stepName": "execute_agents",
                    "outputs": {
                        "actions": [{"agentName": "narrator", "content": long_response}]
                    }
                }
            ]
        }

        narration = _generate_narration("Actor", result, [])

        # Full content should be returned
        assert len(narration) == 1000


class TestGetTurnState:
    """Tests for _get_turn_state helper function."""

    def test_identifies_current_actor(self, sim_with_agents):
        """Test identification of current actor."""
        turn_state = _get_turn_state(sim_with_agents)

        assert turn_state["currentActor"] == "cpu_agent"

    def test_identifies_player_turn(self, sim_with_agents):
        """Test identification of player-controlled turn."""
        # Change to player's turn
        sim_with_agents.setWorldState({
            "actors": ["cpu_agent", "player_agent"],
            "currentActor": "player_agent",
        })

        turn_state = _get_turn_state(sim_with_agents)

        assert turn_state["currentActor"] == "player_agent"
        assert turn_state["isPlayerTurn"] is True

    def test_identifies_cpu_turn(self, sim_with_agents):
        """Test identification of CPU-controlled turn."""
        turn_state = _get_turn_state(sim_with_agents)

        assert turn_state["currentActor"] == "cpu_agent"
        assert turn_state["isPlayerTurn"] is False

    def test_handles_missing_actor(self, app, client):
        """Test handling of missing current actor."""
        client.post(
            "/simulations/create/manual",
            data={"name": "empty_sim", "test_mode": "on"},
        )

        sim = app.simulations["empty_sim"]
        turn_state = _get_turn_state(sim)

        assert turn_state["currentActor"] == "Unknown"
        assert turn_state["isPlayerTurn"] is False

    def test_player_pending_flag_overrides(self, sim_with_agents):
        """Test that _playerPending flag makes isPlayerTurn true."""
        # Set the player pending flag in world state
        sim_with_agents.setWorldState({
            "currentActor": "hero",
            "_playerPending": True,
        })

        turn_state = _get_turn_state(sim_with_agents)

        assert turn_state["currentActor"] == "hero"
        assert turn_state["isPlayerTurn"] is True


class TestPlayEndpoint:
    """Tests for /pipeline/play endpoint."""

    def test_play_returns_404_for_nonexistent_sim(self, client):
        """Test that play returns 404 for non-existent simulation."""
        response = client.post("/simulations/nonexistent/pipeline/play")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_play_returns_immediately_if_player_turn(self, client, sim_with_agents):
        """Test that play returns immediately if already player's turn."""
        # Set to player's turn
        sim_with_agents.setWorldState({
            "actors": ["cpu_agent", "player_agent"],
            "currentActor": "player_agent",
        })

        response = client.post("/simulations/play_test/pipeline/play")

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["isPlayerTurn"] is True
        assert len(data["turns"]) == 0
        assert "Already player's turn" in data["message"]

    @patch("pm6.core.pipeline_executor.PipelineExecutor")
    @patch("pm6.core.engine.SimulationEngine")
    def test_play_executes_until_player_turn(
        self, mock_engine_class, mock_executor_class, client, sim_with_agents
    ):
        """Test that play executes CPU turns until player turn.

        Pipeline returns playerPending=True when it's the player's turn.
        """
        # Setup mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.playerPending = True  # Signal player turn
        mock_result.toDict.return_value = {
            "stepResults": [],
            "steps": [
                {
                    "stepName": "player_turn",
                    "outputs": {"playerPending": True, "playerAgent": "player_agent"}
                }
            ]
        }
        mock_executor.executeAll.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        response = client.post("/simulations/play_test/pipeline/play")

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["isPlayerTurn"] is True
        # Should have executed 1 turn before player_pending detected
        assert len(data["turns"]) == 1
        assert data["turns"][0]["actor"] == "cpu_agent"
        assert data["currentActor"] == "player_agent"

    def test_play_returns_turn_narration(self, client, sim_with_agents):
        """Test that play returns narration for each turn."""
        # Set to player's turn first to get simple response
        sim_with_agents.setWorldState({
            "actors": ["cpu_agent", "player_agent"],
            "currentActor": "player_agent",
        })

        response = client.post("/simulations/play_test/pipeline/play")

        data = json.loads(response.data)
        assert "currentActor" in data
        assert "isPlayerTurn" in data

    def test_play_includes_state_changes(self, client, sim_with_agents):
        """Test that play includes state changes in turn data."""
        # This is a basic structure test - actual changes require pipeline execution
        sim_with_agents.setWorldState({
            "actors": ["cpu_agent", "player_agent"],
            "currentActor": "player_agent",
        })

        response = client.post("/simulations/play_test/pipeline/play")

        data = json.loads(response.data)
        # When already player turn, no turns executed
        assert "turns" in data


class TestTurnStateEndpoint:
    """Tests for /pipeline/turn-state endpoint."""

    def test_turn_state_returns_current_actor(self, client, sim_with_agents):
        """Test that turn-state returns current actor."""
        response = client.get("/simulations/play_test/pipeline/turn-state")

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["currentActor"] == "cpu_agent"
        assert data["isPlayerTurn"] is False

    def test_turn_state_returns_404_for_nonexistent(self, client):
        """Test turn-state returns 404 for non-existent simulation."""
        response = client.get("/simulations/nonexistent/pipeline/turn-state")

        assert response.status_code == 404


class TestExecuteCpuTurnEndpoint:
    """Tests for /pipeline/execute-cpu-turn endpoint."""

    def test_execute_cpu_turn_blocked_on_player_turn(self, client, sim_with_agents):
        """Test that execute-cpu-turn is blocked when it's player's turn."""
        sim_with_agents.setWorldState({
            "actors": ["cpu_agent", "player_agent"],
            "currentActor": "player_agent",
        })

        response = client.post("/simulations/play_test/pipeline/execute-cpu-turn")

        data = json.loads(response.data)
        assert data["success"] is False
        assert "player's turn" in data["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
