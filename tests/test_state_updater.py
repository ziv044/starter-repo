"""Tests for agent state updates."""

import pytest

from pm6.agents import (
    AgentConfig,
    AgentStateUpdater,
    UpdateTrigger,
    extractBoolean,
    extractNumber,
)
from pm6.core import Simulation


class TestAgentStateUpdater:
    """Tests for AgentStateUpdater."""

    def test_always_update(self):
        """Test always-triggered updates."""
        updater = AgentStateUpdater()
        updater.addAlwaysUpdate("agent", "lastResponse", "test", operation="set")

        updates = updater.processInteraction(
            "agent", "input", "response", {"existing": True}
        )

        assert "lastResponse" in updates
        assert updates["lastResponse"]["value"] == "test"
        assert updates["lastResponse"]["operation"] == "set"

    def test_increment_operation(self):
        """Test increment operation."""
        updater = AgentStateUpdater()
        updater.addAlwaysUpdate("agent", "count", 1, operation="increment")

        updates = updater.processInteraction("agent", "input", "response", {})
        state = updater.applyUpdates(updates, {"count": 5})

        assert state["count"] == 6

    def test_append_operation(self):
        """Test append operation."""
        updater = AgentStateUpdater()
        updater.addAlwaysUpdate("agent", "history", "item", operation="append")

        updates = updater.processInteraction("agent", "input", "response", {})
        state = updater.applyUpdates(updates, {"history": ["a", "b"]})

        assert state["history"] == ["a", "b", "item"]

    def test_merge_operation(self):
        """Test merge operation."""
        updater = AgentStateUpdater()
        updater.addAlwaysUpdate(
            "agent", "stats", {"new": "value"}, operation="merge"
        )

        updates = updater.processInteraction("agent", "input", "response", {})
        state = updater.applyUpdates(updates, {"stats": {"old": "data"}})

        assert state["stats"] == {"old": "data", "new": "value"}

    def test_pattern_trigger(self):
        """Test pattern-triggered updates."""
        updater = AgentStateUpdater()
        updater.addPatternUpdate(
            "agent", r"approved|accepted", "decision", "approved"
        )

        # Response matches pattern
        updates = updater.processInteraction(
            "agent", "input", "I have approved the request.", {}
        )
        assert "decision" in updates

        # Response doesn't match
        updates = updater.processInteraction(
            "agent", "input", "I reject the request.", {}
        )
        assert "decision" not in updates

    def test_keyword_trigger(self):
        """Test keyword-triggered updates."""
        updater = AgentStateUpdater()
        updater.addKeywordUpdate(
            "agent", ["war", "conflict"], "status", "hostile"
        )

        # Contains keyword
        updates = updater.processInteraction(
            "agent", "input", "This means war!", {}
        )
        assert "status" in updates

        # No keywords
        updates = updater.processInteraction(
            "agent", "input", "Peace is restored.", {}
        )
        assert "status" not in updates

    def test_conditional_update(self):
        """Test conditional updates."""
        updater = AgentStateUpdater()
        updater.addConditionalUpdate(
            "agent",
            lambda inp, resp, state: state.get("mood") == "angry",
            "escalation", True,
        )

        # Condition met
        updates = updater.processInteraction(
            "agent", "input", "response", {"mood": "angry"}
        )
        assert "escalation" in updates

        # Condition not met
        updates = updater.processInteraction(
            "agent", "input", "response", {"mood": "calm"}
        )
        assert "escalation" not in updates

    def test_callback(self):
        """Test custom callback for updates."""
        def myCallback(agentName, userInput, response, state):
            return {
                "lastAgent": agentName,
                "inputLength": len(userInput),
            }

        updater = AgentStateUpdater()
        updater.addCallback("agent", myCallback)

        updates = updater.processInteraction(
            "agent", "hello world", "response", {}
        )

        assert "lastAgent" in updates
        assert "inputLength" in updates

    def test_interaction_counter(self):
        """Test interaction counter."""
        updater = AgentStateUpdater()
        updater.addInteractionCounter("agent", "interactions")

        updates = updater.processInteraction("agent", "input", "response", {})
        state = updater.applyUpdates(updates, {"interactions": 3})

        assert state["interactions"] == 4

    def test_callable_value(self):
        """Test callable values in updates."""
        updater = AgentStateUpdater()
        updater.addAlwaysUpdate(
            "agent",
            "responseLength",
            lambda inp, resp, state: len(resp),
        )

        updates = updater.processInteraction(
            "agent", "input", "short response", {}
        )

        assert updates["responseLength"]["value"] == 14  # len("short response")


class TestHelperFunctions:
    """Tests for helper extraction functions."""

    def test_extract_number(self):
        """Test number extraction."""
        assert extractNumber("The budget is 1000 dollars") == 1000
        assert extractNumber("Price: $45.99") == 45.99
        assert extractNumber("Negative: -10") == -10
        assert extractNumber("No numbers here") is None

    def test_extract_number_with_pattern(self):
        """Test number extraction with pattern."""
        result = extractNumber(
            "Score: 85/100", r"Score: (\d+)"
        )
        assert result == 85

    def test_extract_boolean(self):
        """Test boolean extraction."""
        assert extractBoolean("Yes, I agree") is True
        assert extractBoolean("No, I refuse") is False  # "disagree" contains "agree"
        assert extractBoolean("Maybe later") is None

    def test_extract_boolean_custom_keywords(self):
        """Test boolean extraction with custom keywords."""
        result = extractBoolean(
            "Affirmative!", trueKeywords=["affirmative", "roger"]
        )
        assert result is True


class TestSimulationStateUpdates:
    """Tests for state updates in Simulation."""

    def test_add_state_update_rule(self, tmp_path):
        """Test adding state update rules via Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response 1"],
        )

        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        sim.addStateUpdateRule("test", "lastAgent", "test")
        sim.addMockResponse("Test response")

        sim.interact("test", "Hello")

        assert sim.getWorldState().get("lastAgent") == "test"

    def test_add_interaction_counter(self, tmp_path):
        """Test interaction counter via Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1", "R2", "R3"],
        )

        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        sim.addInteractionCounter("test", "turns")

        sim.interact("test", "Hello 1")
        sim.interact("test", "Hello 2")
        sim.interact("test", "Hello 3")

        assert sim.getWorldState().get("turns") == 3

    def test_keyword_update_rule(self, tmp_path):
        """Test keyword-based updates."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        sim.addStateUpdateRule(
            "test",
            "negotiation",
            "success",
            trigger="keyword",
            triggerValue=["agree", "accept"],
        )

        # Response with keyword
        sim.addMockResponse("I accept your proposal")
        sim.interact("test", "What do you think?")

        assert sim.getWorldState().get("negotiation") == "success"

    def test_disable_auto_updates(self, tmp_path):
        """Test disabling automatic state updates."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response"],
        )

        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        sim.addInteractionCounter("test", "count")
        sim.disableAutoStateUpdates()

        sim.interact("test", "Hello")

        # Counter should not increment
        assert sim.getWorldState().get("count") is None

    def test_state_update_callback(self, tmp_path):
        """Test custom callback via Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Some response text"],
        )

        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        def updateCallback(agentName, userInput, response, state):
            return {"responseChars": len(response)}

        sim.addStateUpdateCallback("test", updateCallback)

        sim.interact("test", "Hello")

        assert sim.getWorldState().get("responseChars") == 18  # len("Some response text")

    def test_state_updater_property(self, tmp_path):
        """Test accessing state updater directly."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        updater = sim.stateUpdater
        assert updater is not None
        assert isinstance(updater, AgentStateUpdater)
