"""Tests for the core simulation module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pm6 import AgentConfig, Simulation
from pm6.exceptions import AgentNotFoundError, SimulationError


class TestSimulation:
    """Tests for Simulation class."""

    def test_create_simulation(self):
        """Test creating a simulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            assert sim.name == "test"
            assert sim.listAgents() == []

    def test_register_agent(self):
        """Test registering an agent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="Prime Minister")
            sim.registerAgent(agent)

            assert "pm" in sim.listAgents()
            assert sim.getAgent("pm").role == "Prime Minister"

    def test_register_duplicate_agent_raises(self):
        """Test registering a duplicate agent raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)

            with pytest.raises(SimulationError):
                sim.registerAgent(agent)

    def test_get_nonexistent_agent_raises(self):
        """Test getting non-existent agent raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            with pytest.raises(AgentNotFoundError):
                sim.getAgent("nonexistent")

    def test_world_state_management(self):
        """Test world state management."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            # Set initial state
            sim.setWorldState({"approval": 50, "economy": 10})
            state = sim.getWorldState()
            assert state["approval"] == 50
            assert state["economy"] == 10

            # Update state
            sim.updateWorldState({"approval": 60})
            state = sim.getWorldState()
            assert state["approval"] == 60
            assert state["economy"] == 10

    def test_checkpoint_save_load(self):
        """Test saving and loading checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            # Setup
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)
            sim.setWorldState({"approval": 75})

            # Save checkpoint
            sim.saveCheckpoint("checkpoint1")
            assert "checkpoint1" in sim.listCheckpoints()

            # Modify state
            sim.setWorldState({"approval": 25})
            assert sim.getWorldState()["approval"] == 25

            # Load checkpoint
            sim.loadCheckpoint("checkpoint1")
            assert sim.getWorldState()["approval"] == 75

    def test_stats(self):
        """Test getting simulation statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)

            stats = sim.getStats()
            assert stats["name"] == "test"
            assert stats["agentCount"] == 1
            assert "costs" in stats
            assert "cache" in stats

    def test_lifecycle(self):
        """Test simulation lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            assert not sim.isRunning
            sim.start()
            assert sim.isRunning
            sim.stop()
            assert not sim.isRunning


class TestSimulationInteraction:
    """Tests for simulation interactions (mocked LLM)."""

    @patch("pm6.core.simulation.AnthropicClient")
    def test_interact_with_agent(self, mock_client_class):
        """Test interacting with an agent."""
        # Setup mock
        mock_client = MagicMock()
        mock_client.generateAgentResponse.return_value = {
            "content": "This is a test response.",
            "model": "claude-sonnet-4-20250514",
            "usage": {"inputTokens": 100, "outputTokens": 50, "cachedTokens": 0},
        }
        mock_client_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir), enableCache=False)
            agent = AgentConfig(
                name="pm",
                role="Prime Minister",
                systemPrompt="You are the PM.",
            )
            sim.registerAgent(agent)

            response = sim.interact("pm", "What is your budget plan?")

            assert response.agentName == "pm"
            assert response.content == "This is a test response."
            assert not response.fromCache

    @patch("pm6.core.simulation.AnthropicClient")
    def test_interact_with_context(self, mock_client_class):
        """Test interaction with context."""
        mock_client = MagicMock()
        mock_client.generateAgentResponse.return_value = {
            "content": "Response with context.",
            "model": "claude-sonnet-4-20250514",
            "usage": {"inputTokens": 100, "outputTokens": 50, "cachedTokens": 0},
        }
        mock_client_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir), enableCache=False)
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)

            response = sim.interact(
                "pm",
                "What do you think?",
                context={"currentBudget": "1.2T"},
            )

            assert response.content == "Response with context."


class TestSimulationSaveResume:
    """Tests for simulation save/resume functionality (FR28)."""

    def test_save_simulation(self):
        """Test saving simulation state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="Prime Minister")
            sim.registerAgent(agent)
            sim.setWorldState({"approval": 75, "year": 2025})

            # Save with explicit name
            saveName = sim.saveSimulation("my_save")
            assert saveName == "my_save"
            assert sim.hasSave("my_save")

    def test_save_simulation_default_name(self):
        """Test saving with default autosave name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            saveName = sim.saveSimulation()
            assert saveName == "autosave"
            assert sim.hasSave("autosave")

    def test_resume_simulation_restores_world_state(self):
        """Test resuming restores world state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            sim.setWorldState({"approval": 85, "crisis": "economic"})
            sim.saveSimulation("state1")

            # Modify state
            sim.setWorldState({"approval": 10, "crisis": None})
            assert sim.getWorldState()["approval"] == 10

            # Resume from save
            sim.resumeSimulation("state1")
            state = sim.getWorldState()
            assert state["approval"] == 85
            assert state["crisis"] == "economic"

    def test_resume_simulation_restores_agents(self):
        """Test resuming restores registered agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent1 = AgentConfig(name="pm", role="Prime Minister")
            agent2 = AgentConfig(name="chancellor", role="Chancellor")
            sim.registerAgent(agent1)
            sim.registerAgent(agent2)
            sim.saveSimulation("with_agents")

            # Create new simulation and resume
            sim2 = Simulation("test", dbPath=Path(tmpdir))
            assert sim2.listAgents() == []

            sim2.resumeSimulation("with_agents")
            agents = sim2.listAgents()
            assert "pm" in agents
            assert "chancellor" in agents
            assert sim2.getAgent("pm").role == "Prime Minister"

    def test_list_saves(self):
        """Test listing available saves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            # Initially empty
            assert sim.listSaves() == []

            # Create some saves
            sim.saveSimulation("save1")
            sim.saveSimulation("save2")
            sim.saveSimulation("save3")

            saves = sim.listSaves()
            assert len(saves) == 3
            assert "save1" in saves
            assert "save2" in saves
            assert "save3" in saves

    def test_delete_save(self):
        """Test deleting a save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            sim.saveSimulation("to_delete")
            assert sim.hasSave("to_delete")

            sim.deleteSave("to_delete")
            assert not sim.hasSave("to_delete")
            assert "to_delete" not in sim.listSaves()

    def test_has_save(self):
        """Test checking if a save exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            assert not sim.hasSave("nonexistent")
            sim.saveSimulation("exists")
            assert sim.hasSave("exists")

    def test_resume_from_class_method(self):
        """Test resumeFrom class method creates and resumes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save a simulation
            sim1 = Simulation("test_sim", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim1.registerAgent(agent)
            sim1.setWorldState({"status": "saved"})
            sim1.saveSimulation("my_checkpoint")

            # Resume using class method
            sim2 = Simulation.resumeFrom("test_sim", "my_checkpoint", dbPath=Path(tmpdir))

            assert sim2.name == "test_sim"
            assert "pm" in sim2.listAgents()
            assert sim2.getWorldState()["status"] == "saved"

    def test_resume_nonexistent_save_raises(self):
        """Test resuming from nonexistent save raises error."""
        from pm6.exceptions import SessionNotFoundError

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            with pytest.raises(SessionNotFoundError):
                sim.resumeSimulation("nonexistent")

    def test_save_overwrites_existing(self):
        """Test saving with same name overwrites previous save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            # Save initial state
            sim.setWorldState({"version": 1})
            sim.saveSimulation("overwrite_test")

            # Save new state with same name
            sim.setWorldState({"version": 2})
            sim.saveSimulation("overwrite_test")

            # Create new sim and resume
            sim2 = Simulation("test", dbPath=Path(tmpdir))
            sim2.resumeSimulation("overwrite_test")
            assert sim2.getWorldState()["version"] == 2

    def test_saves_separate_from_checkpoints(self):
        """Test saves don't appear in checkpoint list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            sim.saveSimulation("my_save")
            sim.saveCheckpoint("my_checkpoint")

            saves = sim.listSaves()
            checkpoints = sim.listCheckpoints()

            assert "my_save" in saves
            assert "my_save" not in checkpoints
            assert "my_checkpoint" in checkpoints
            assert "my_checkpoint" not in saves


class TestSessionExport:
    """Tests for session data export functionality (FR29)."""

    def test_export_to_file_json(self):
        """Test exporting simulation to JSON file."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="Prime Minister")
            sim.registerAgent(agent)
            sim.setWorldState({"year": 2025})

            exportPath = Path(tmpdir) / "export.json"
            result = sim.exportToFile(exportPath)

            assert result == exportPath
            assert exportPath.exists()

            with open(exportPath) as f:
                data = json.load(f)

            assert data["simulationName"] == "test"
            assert "exportedAt" in data
            assert data["worldState"]["year"] == 2025
            assert "pm" in data["agents"]

    def test_export_to_file_csv(self):
        """Test exporting simulation to CSV file."""
        import csv

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            exportPath = Path(tmpdir) / "export.csv"

            result = sim.exportToFile(exportPath, format="csv")

            assert result == exportPath
            assert exportPath.exists()

            with open(exportPath) as f:
                reader = csv.reader(f)
                header = next(reader)
                assert "turn" in header
                assert "agent" in header
                assert "content" in header

    def test_export_to_file_creates_directory(self):
        """Test export creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            exportPath = Path(tmpdir) / "nested" / "dirs" / "export.json"
            sim.exportToFile(exportPath)

            assert exportPath.exists()

    def test_export_to_file_options(self):
        """Test export with selective options."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            exportPath = Path(tmpdir) / "export.json"

            # Export without history and agents
            sim.exportToFile(
                exportPath,
                includeHistory=False,
                includeAgents=False,
            )

            with open(exportPath) as f:
                data = json.load(f)

            assert "history" not in data
            assert "agents" not in data
            assert "simulationName" in data

    def test_export_history_json(self):
        """Test exporting history to JSON."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            exportPath = Path(tmpdir) / "history.json"

            sim.exportHistory(exportPath)

            assert exportPath.exists()
            with open(exportPath) as f:
                data = json.load(f)
            assert isinstance(data, list)

    def test_export_history_csv(self):
        """Test exporting history to CSV."""
        import csv

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            exportPath = Path(tmpdir) / "history.csv"

            sim.exportHistory(exportPath, format="csv")

            assert exportPath.exists()
            with open(exportPath) as f:
                reader = csv.reader(f)
                header = next(reader)
                assert "turn" in header
                assert "agent" in header

    def test_export_history_with_filter(self):
        """Test exporting history with agent filter."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))

            # Add some mock history
            sim._history = [
                {"agentName": "pm", "content": "Response 1"},
                {"agentName": "chancellor", "content": "Response 2"},
                {"agentName": "pm", "content": "Response 3"},
            ]

            exportPath = Path(tmpdir) / "filtered.json"
            sim.exportHistory(exportPath, agentFilter="pm")

            with open(exportPath) as f:
                data = json.load(f)

            assert len(data) == 2
            assert all(entry["agentName"] == "pm" for entry in data)

    def test_export_cost_report_json(self):
        """Test exporting cost report to JSON."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir), enableCostTracking=True)
            exportPath = Path(tmpdir) / "costs.json"

            sim.exportCostReport(exportPath)

            assert exportPath.exists()
            with open(exportPath) as f:
                data = json.load(f)

            assert data["simulationName"] == "test"
            assert "summary" in data
            assert "tokenBudget" in data

    def test_export_cost_report_csv(self):
        """Test exporting cost report to CSV."""
        import csv

        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir), enableCostTracking=True)
            exportPath = Path(tmpdir) / "costs.csv"

            sim.exportCostReport(exportPath, format="csv")

            assert exportPath.exists()
            with open(exportPath) as f:
                reader = csv.reader(f)
                header = next(reader)
                assert "metric" in header
                assert "value" in header

    def test_get_exportable_data(self):
        """Test getting all exportable data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)
            sim.setWorldState({"status": "active"})

            data = sim.getExportableData()

            assert data["simulationName"] == "test"
            assert "pm" in data["agents"]
            assert data["worldState"]["status"] == "active"
            assert "stats" in data
            assert "tokenUsage" in data

    def test_export_invalid_format_raises(self):
        """Test that invalid format raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            exportPath = Path(tmpdir) / "export.xyz"

            with pytest.raises(ValueError, match="Unsupported export format"):
                sim.exportToFile(exportPath, format="xyz")
