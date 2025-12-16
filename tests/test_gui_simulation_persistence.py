"""TDD tests for GUI simulation creation and persistence."""

import shutil
import tempfile
from pathlib import Path

import pytest

from simConfigGui.app import create_app


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


class TestSimulationCreation:
    """Test simulation creation through the GUI."""

    def test_manual_create_simulation_success(self, client, app, temp_db):
        """Test creating a simulation via manual form."""
        # Create simulation
        response = client.post(
            "/simulations/create/manual",
            data={"name": "test_sim", "test_mode": "on"},
            follow_redirects=True,
        )

        # Assert redirect to simulation view (success)
        assert response.status_code == 200

        # Assert simulation exists in memory
        assert "test_sim" in app.simulations

        # Assert simulation directory created on disk
        sim_dir = temp_db / "test_sim"
        assert sim_dir.exists(), f"Simulation directory not created at {sim_dir}"

        # Assert agents folder created
        agents_dir = sim_dir / "agents"
        assert agents_dir.exists(), f"Agents directory not created at {agents_dir}"

    def test_manual_create_simulation_with_name_validation(self, client, app):
        """Test that empty name is rejected."""
        response = client.post(
            "/simulations/create/manual",
            data={"name": "", "test_mode": "on"},
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()
        assert len(app.simulations) == 0

    def test_manual_create_duplicate_simulation_rejected(self, client, app):
        """Test that duplicate simulation names are rejected."""
        # Create first simulation
        client.post(
            "/simulations/create/manual",
            data={"name": "duplicate_test", "test_mode": "on"},
        )

        # Try to create duplicate
        response = client.post(
            "/simulations/create/manual",
            data={"name": "duplicate_test", "test_mode": "on"},
            follow_redirects=True,
        )

        assert b"already exists" in response.data.lower()
        # Should still only have one simulation
        assert len(app.simulations) == 1


class TestSimulationPersistence:
    """Test simulation persistence across app restarts."""

    def test_simulation_persists_after_restart(self, temp_db):
        """Test that simulations are reloaded after app restart."""
        # Create app and simulation
        app1 = create_app("testing")
        app1.config["DB_PATH"] = str(temp_db)
        app1.db_path = temp_db
        app1.simulations = {}

        with app1.test_client() as client:
            client.post(
                "/simulations/create/manual",
                data={"name": "persistent_sim", "test_mode": "on"},
            )

        # Verify simulation was created
        assert "persistent_sim" in app1.simulations

        # Verify directory structure on disk
        sim_dir = temp_db / "persistent_sim"
        assert sim_dir.exists(), "Simulation directory not created"

        agents_dir = sim_dir / "agents"
        assert agents_dir.exists(), "Agents directory not created"

        # Create NEW app instance (simulating restart)
        app2 = create_app("testing")
        app2.config["DB_PATH"] = str(temp_db)
        app2.db_path = temp_db
        app2.simulations = {}

        # Manually trigger reload (simulating what happens on startup)
        from simConfigGui.app import _load_existing_simulations
        _load_existing_simulations(app2)

        # Verify simulation was reloaded
        assert "persistent_sim" in app2.simulations, \
            f"Simulation not reloaded. Found: {list(app2.simulations.keys())}"

    def test_simulation_with_agents_persists(self, temp_db):
        """Test that simulations with agents persist correctly."""
        # Create app and simulation with agent
        app1 = create_app("testing")
        app1.config["DB_PATH"] = str(temp_db)
        app1.db_path = temp_db
        app1.simulations = {}

        with app1.test_client() as client:
            # Create simulation
            client.post(
                "/simulations/create/manual",
                data={"name": "agent_sim", "test_mode": "on"},
            )

            # Add an agent
            client.post(
                "/simulations/agent_sim/agents/add",
                data={
                    "name": "test_agent",
                    "role": "Test Role",
                    "systemPrompt": "You are a test agent",
                    "model": "claude-sonnet-4-20250514",
                    "memoryPolicy": "summary",
                    "controlledBy": "cpu",
                    "initiative": "0.5",
                    "agentType": "entity",
                },
            )

        # Verify agent file exists
        agent_file = temp_db / "agent_sim" / "agents" / "test_agent.json"
        assert agent_file.exists(), f"Agent file not created at {agent_file}"

        # Create NEW app instance
        app2 = create_app("testing")
        app2.config["DB_PATH"] = str(temp_db)
        app2.db_path = temp_db
        app2.simulations = {}

        from simConfigGui.app import _load_existing_simulations
        _load_existing_simulations(app2)

        # Verify simulation and agent were reloaded
        assert "agent_sim" in app2.simulations
        sim = app2.simulations["agent_sim"]
        agents = sim.listAgents()
        assert "test_agent" in agents, f"Agent not reloaded. Found: {agents}"


class TestSimulationStructure:
    """Test the correct directory structure is created."""

    def test_simulation_creates_correct_structure(self, client, app, temp_db):
        """Test that simulation creates the expected directory structure."""
        client.post(
            "/simulations/create/manual",
            data={"name": "structure_test", "test_mode": "on"},
        )

        sim_dir = temp_db / "structure_test"

        # Check directory exists
        assert sim_dir.exists()
        assert sim_dir.is_dir()

        # Check agents subdirectory
        agents_dir = sim_dir / "agents"
        assert agents_dir.exists()
        assert agents_dir.is_dir()

    def test_agent_creates_json_file(self, client, app, temp_db):
        """Test that adding an agent creates a JSON file."""
        # Create simulation
        client.post(
            "/simulations/create/manual",
            data={"name": "agent_file_test", "test_mode": "on"},
        )

        # Add agent
        client.post(
            "/simulations/agent_file_test/agents/add",
            data={
                "name": "file_agent",
                "role": "Test",
                "systemPrompt": "Test prompt",
                "model": "claude-sonnet-4-20250514",
                "memoryPolicy": "summary",
                "controlledBy": "cpu",
                "initiative": "0.5",
                "agentType": "entity",
            },
        )

        # Check agent file exists
        agent_file = temp_db / "agent_file_test" / "agents" / "file_agent.json"
        assert agent_file.exists(), f"Agent file not found at {agent_file}"

        # Check file contains valid JSON
        import json
        with open(agent_file) as f:
            data = json.load(f)

        assert data["name"] == "file_agent"
        assert data["role"] == "Test"


class TestAutoLoadOnStartup:
    """Test automatic loading of simulations on app startup."""

    def test_app_loads_existing_simulations(self, temp_db):
        """Test that app loads existing simulations from disk on startup."""
        # Manually create simulation structure on disk
        sim_dir = temp_db / "manual_sim"
        agents_dir = sim_dir / "agents"
        agents_dir.mkdir(parents=True)

        # Create a dummy agent file
        import json
        agent_file = agents_dir / "dummy_agent.json"
        agent_data = {
            "name": "dummy_agent",
            "role": "Dummy",
            "systemPrompt": "Test",
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "summary",
            "controlledBy": "cpu",
            "initiative": 0.5,
            "metadata": {"agentType": "entity"},
        }
        with open(agent_file, "w") as f:
            json.dump(agent_data, f)

        # Create app - should auto-load the simulation
        app = create_app("testing")
        app.db_path = temp_db

        from simConfigGui.app import _load_existing_simulations
        _load_existing_simulations(app)

        # Verify simulation was loaded
        assert "manual_sim" in app.simulations
        assert "dummy_agent" in app.simulations["manual_sim"].listAgents()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
