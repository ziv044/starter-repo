"""Tests for the testing module."""

import pytest

from pm6.agents import AgentConfig
from pm6.core import Simulation
from pm6.testing import MockAnthropicClient, MockResponse


class TestMockAnthropicClient:
    """Tests for MockAnthropicClient."""

    def test_default_response(self):
        """Test default mock response."""
        client = MockAnthropicClient(defaultResponse="Default test response")
        response = client.createMessage(messages=[{"role": "user", "content": "Hello"}])

        assert response["content"] == "Default test response"
        assert "usage" in response

    def test_static_response(self):
        """Test static response setting."""
        client = MockAnthropicClient()
        client.setStaticResponse("Static response")

        response1 = client.createMessage(messages=[{"role": "user", "content": "Test 1"}])
        response2 = client.createMessage(messages=[{"role": "user", "content": "Test 2"}])

        assert response1["content"] == "Static response"
        assert response2["content"] == "Static response"

    def test_response_queue(self):
        """Test response queue (FIFO)."""
        client = MockAnthropicClient()
        client.addResponses(["First", "Second", "Third"])

        r1 = client.createMessage(messages=[{"role": "user", "content": "1"}])
        r2 = client.createMessage(messages=[{"role": "user", "content": "2"}])
        r3 = client.createMessage(messages=[{"role": "user", "content": "3"}])

        assert r1["content"] == "First"
        assert r2["content"] == "Second"
        assert r3["content"] == "Third"

    def test_mock_response_with_metadata(self):
        """Test MockResponse with custom metadata."""
        client = MockAnthropicClient()
        client.addResponse(
            MockResponse(
                content="Custom response",
                model="claude-opus-4-20250514",
                inputTokens=200,
                outputTokens=100,
            )
        )

        response = client.createMessage(messages=[{"role": "user", "content": "Test"}])

        assert response["content"] == "Custom response"
        assert response["usage"]["inputTokens"] == 200
        assert response["usage"]["outputTokens"] == 100

    def test_call_tracking(self):
        """Test call count and history tracking."""
        client = MockAnthropicClient()
        client.setStaticResponse("Response")

        assert client.callCount == 0

        client.createMessage(messages=[{"role": "user", "content": "First"}])
        client.createMessage(messages=[{"role": "user", "content": "Second"}])

        assert client.callCount == 2
        assert len(client.callHistory) == 2

    def test_was_called_with(self):
        """Test call content verification."""
        client = MockAnthropicClient()
        client.setStaticResponse("Response")

        client.createMessage(messages=[{"role": "user", "content": "Hello world"}])

        assert client.wasCalledWith("Hello")
        assert client.wasCalledWith("world")
        assert not client.wasCalledWith("goodbye")

    def test_reset(self):
        """Test state reset."""
        client = MockAnthropicClient()
        client.setStaticResponse("Response")
        client.createMessage(messages=[{"role": "user", "content": "Test"}])

        assert client.callCount == 1

        client.reset()

        assert client.callCount == 0
        assert len(client.callHistory) == 0

    def test_generate_agent_response(self):
        """Test generateAgentResponse method."""
        client = MockAnthropicClient()
        client.setStaticResponse("Agent response")

        response = client.generateAgentResponse(
            agentSystemPrompt="You are a helpful assistant",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response["content"] == "Agent response"

    def test_compact(self):
        """Test message compaction."""
        client = MockAnthropicClient()

        messages = [
            {"role": "user", "content": f"Message {i}"} for i in range(10)
        ]

        compacted = client.compact(messages, keepRecent=3)

        assert len(compacted) == 4  # 1 summary + 3 recent
        assert "[Previous conversation summary" in compacted[0]["content"]

    def test_summarize(self):
        """Test summarization."""
        client = MockAnthropicClient()

        summary = client.summarize("This is a long text that needs summarization")

        assert "[Summary:" in summary


class TestSimulationTestMode:
    """Tests for Simulation in test mode."""

    def test_create_test_simulation(self, tmp_path):
        """Test creating simulation in test mode."""
        sim = Simulation(name="test", dbPath=tmp_path, testMode=True)

        assert sim.isTestMode
        assert sim.mockClient is not None

    def test_factory_method(self, tmp_path):
        """Test createTestSimulation factory method."""
        sim = Simulation.createTestSimulation(
            name="factory_test",
            dbPath=tmp_path,
            responses=["Response 1", "Response 2"],
            worldState={"key": "value"},
        )

        assert sim.isTestMode
        assert sim.getWorldState() == {"key": "value"}

    def test_set_mock_response(self, tmp_path):
        """Test setting mock response."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.setMockResponse("Test response")

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        response = sim.interact("TestAgent", "Hello")

        assert response.content == "Test response"

    def test_add_mock_responses(self, tmp_path):
        """Test adding multiple mock responses."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["First", "Second"],
        )

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        r1 = sim.interact("TestAgent", "Hello")
        r2 = sim.interact("TestAgent", "Goodbye")

        assert r1.content == "First"
        assert r2.content == "Second"

    def test_mock_call_count(self, tmp_path):
        """Test mock call tracking."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1", "R2"],
        )

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        assert sim.getMockCallCount() == 0

        sim.interact("TestAgent", "First")
        assert sim.getMockCallCount() == 1

        sim.interact("TestAgent", "Second")
        assert sim.getMockCallCount() == 2

    def test_mock_call_history(self, tmp_path):
        """Test mock call history."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response"],
        )

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        sim.interact("TestAgent", "Hello world")

        history = sim.getMockCallHistory()
        assert len(history) == 1

    def test_reset_mock_state(self, tmp_path):
        """Test resetting mock state."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1"],
        )

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        sim.interact("TestAgent", "Test")
        assert sim.getMockCallCount() == 1

        sim.resetMockState()
        assert sim.getMockCallCount() == 0

    def test_non_test_mode_raises(self, tmp_path):
        """Test that test mode methods raise in non-test mode."""
        sim = Simulation(name="test", dbPath=tmp_path, testMode=False)

        from pm6.exceptions import SimulationError

        with pytest.raises(SimulationError, match="requires test mode"):
            sim.setMockResponse("test")

        with pytest.raises(SimulationError, match="requires test mode"):
            sim.getMockCallCount()

    def test_custom_mock_client(self, tmp_path):
        """Test providing a custom mock client."""
        client = MockAnthropicClient()
        client.setStaticResponse("Custom client response")

        sim = Simulation(name="test", dbPath=tmp_path, testMode=True, mockClient=client)

        agent = AgentConfig(name="TestAgent", role="Test", systemPrompt="You are a test agent")
        sim.registerAgent(agent)

        response = sim.interact("TestAgent", "Hello")

        assert response.content == "Custom client response"
        assert sim.mockClient is client
