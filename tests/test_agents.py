"""Tests for the agents module."""

import pytest

from pm6.agents import AgentConfig, AgentRouter, MemoryManager, MemoryPolicy


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_create_basic_agent(self):
        """Test creating a basic agent configuration."""
        agent = AgentConfig(name="test", role="Test Agent")
        assert agent.name == "test"
        assert agent.role == "Test Agent"
        assert agent.memoryPolicy == MemoryPolicy.SUMMARY

    def test_create_agent_with_all_fields(self):
        """Test creating agent with all fields specified."""
        agent = AgentConfig(
            name="pm",
            role="Prime Minister",
            systemPrompt="You are the PM.",
            model="claude-opus-4-20250514",
            memoryPolicy=MemoryPolicy.FULL,
            situationTypes=["budget", "crisis"],
        )
        assert agent.name == "pm"
        assert agent.role == "Prime Minister"
        assert agent.systemPrompt == "You are the PM."
        assert agent.model == "claude-opus-4-20250514"
        assert agent.memoryPolicy == MemoryPolicy.FULL
        assert agent.situationTypes == ["budget", "crisis"]

    def test_agent_serialization(self):
        """Test agent can be serialized to dict."""
        agent = AgentConfig(name="test", role="Test")
        data = agent.model_dump()
        assert data["name"] == "test"
        assert data["role"] == "Test"

    def test_agent_deserialization(self):
        """Test agent can be deserialized from dict."""
        data = {"name": "test", "role": "Test Agent"}
        agent = AgentConfig.model_validate(data)
        assert agent.name == "test"
        assert agent.role == "Test Agent"


class TestMemoryPolicy:
    """Tests for MemoryPolicy."""

    def test_policy_values(self):
        """Test memory policy enum values."""
        assert MemoryPolicy.FULL.value == "full"
        assert MemoryPolicy.SUMMARY.value == "summary"
        assert MemoryPolicy.SELECTIVE.value == "selective"
        assert MemoryPolicy.NONE.value == "none"


class TestMemoryManager:
    """Tests for MemoryManager."""

    def test_default_policy(self):
        """Test default memory policy."""
        manager = MemoryManager()
        assert manager.policy == MemoryPolicy.SUMMARY

    def test_full_memory_retains_all(self):
        """Test FULL policy retains all interactions."""
        manager = MemoryManager(policy=MemoryPolicy.FULL)
        manager.addInteraction({"role": "user", "content": "Hello"})
        manager.addInteraction({"role": "assistant", "content": "Hi"})
        assert len(manager.getHistory()) == 2

    def test_none_memory_retains_nothing(self):
        """Test NONE policy retains nothing."""
        manager = MemoryManager(policy=MemoryPolicy.NONE)
        manager.addInteraction({"role": "user", "content": "Hello"})
        assert len(manager.getHistory()) == 0

    def test_needs_compaction(self):
        """Test compaction detection."""
        manager = MemoryManager(policy=MemoryPolicy.SUMMARY, maxTurns=3)
        manager.addInteraction({"role": "user", "content": "1"})
        manager.addInteraction({"role": "assistant", "content": "2"})
        assert not manager.needsCompaction()

        manager.addInteraction({"role": "user", "content": "3"})
        assert manager.needsCompaction()


class TestAgentRouter:
    """Tests for AgentRouter."""

    def test_add_and_get_agent(self):
        """Test adding and retrieving an agent."""
        router = AgentRouter()
        agent = AgentConfig(name="test", role="Test")
        router.addAgent(agent)

        retrieved = router.getAgent("test")
        assert retrieved is not None
        assert retrieved.name == "test"

    def test_get_nonexistent_agent(self):
        """Test getting a non-existent agent returns None."""
        router = AgentRouter()
        assert router.getAgent("nonexistent") is None

    def test_route_by_name(self):
        """Test routing by agent name."""
        router = AgentRouter()
        agent = AgentConfig(name="pm", role="PM")
        router.addAgent(agent)

        routed = router.routeInteraction(agentName="pm")
        assert len(routed) == 1
        assert routed[0].name == "pm"

    def test_route_by_situation(self):
        """Test routing by situation type."""
        router = AgentRouter()
        agent1 = AgentConfig(name="pm", role="PM", situationTypes=["budget"])
        agent2 = AgentConfig(name="fm", role="FM", situationTypes=["budget", "economy"])
        router.addAgent(agent1)
        router.addAgent(agent2)

        routed = router.routeInteraction(situationType="budget")
        assert len(routed) == 2

        routed = router.routeInteraction(situationType="economy")
        assert len(routed) == 1
        assert routed[0].name == "fm"
