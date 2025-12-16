"""Tests for automated scenario testing."""

import pytest

from pm6.agents import AgentConfig
from pm6.core import Simulation
from pm6.testing import (
    AssertionType,
    ScenarioBuilder,
    ScenarioResult,
    ScenarioTester,
    TestAssertion,
    TestScenario,
    TestStep,
)


class TestScenarioBuilder:
    """Tests for ScenarioBuilder."""

    def test_basic_scenario(self):
        """Test building a basic scenario."""
        scenario = (
            ScenarioBuilder("basic_test")
            .describe("A simple test scenario")
            .interact("agent", "Hello", "Hi there!")
            .build()
        )

        assert scenario.name == "basic_test"
        assert scenario.description == "A simple test scenario"
        assert len(scenario.steps) == 1

    def test_scenario_with_state(self):
        """Test scenario with initial state."""
        scenario = (
            ScenarioBuilder("state_test")
            .withState({"mood": "happy", "counter": 0})
            .interact("agent", "How are you?", "I'm great!")
            .build()
        )

        assert scenario.initialState == {"mood": "happy", "counter": 0}

    def test_scenario_with_assertions(self):
        """Test scenario with assertions."""
        scenario = (
            ScenarioBuilder("assertion_test")
            .interact("agent", "Hello", "Hello! How are you?")
            .expectResponseContains("Hello")
            .expectState("greeted", True)
            .build()
        )

        assert len(scenario.steps) == 1
        assert len(scenario.steps[0].assertions) == 2

    def test_multiple_steps(self):
        """Test scenario with multiple steps."""
        scenario = (
            ScenarioBuilder("multi_step")
            .interact("agent", "Step 1", "Response 1")
            .expectResponseContains("Response")
            .interact("agent", "Step 2", "Response 2")
            .expectResponseContains("Response")
            .build()
        )

        assert len(scenario.steps) == 2

    def test_set_state_step(self):
        """Test setState step."""
        scenario = (
            ScenarioBuilder("set_state_test")
            .setState({"key": "value"})
            .interact("agent", "After state change", "Response")
            .build()
        )

        assert scenario.steps[0].action == "setState"

    def test_tags(self):
        """Test scenario tags."""
        scenario = (
            ScenarioBuilder("tagged_test")
            .withTags("smoke", "fast")
            .interact("agent", "Test", "Response")
            .build()
        )

        assert "smoke" in scenario.tags
        assert "fast" in scenario.tags

    def test_pattern_assertion(self):
        """Test pattern-based assertions."""
        scenario = (
            ScenarioBuilder("pattern_test")
            .interact("agent", "What time?", "The time is 10:30")
            .expectResponseMatches(r"\d+:\d+")
            .build()
        )

        assertion = scenario.steps[0].assertions[0]
        assert assertion.type == AssertionType.RESPONSE_PATTERN


class TestScenarioTester:
    """Tests for ScenarioTester."""

    def test_run_simple_scenario(self, tmp_path):
        """Test running a simple scenario."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("simple")
            .interact("agent", "Hello", "Hi there!")
            .expectResponseContains("Hi")
            .build()
        )

        result = tester.runScenario(scenario)

        assert result.passed
        assert result.totalAssertions == 1
        assert result.passedAssertions == 1

    def test_scenario_with_state_assertion(self, tmp_path):
        """Test scenario with state assertion."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            worldState={"counter": 0},
        )
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))
        sim.addInteractionCounter("agent", "counter")

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("state_test")
            .withState({"counter": 0})
            .interact("agent", "Hello", "Hi!")
            .expectState("counter", 1)
            .build()
        )

        result = tester.runScenario(scenario)

        assert result.passed

    def test_failing_scenario(self, tmp_path):
        """Test scenario that fails."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("failing")
            .interact("agent", "Hello", "Hi there!")
            .expectResponseContains("goodbye")  # Won't match
            .build()
        )

        result = tester.runScenario(scenario)

        assert not result.passed
        assert result.passedAssertions == 0

    def test_run_multiple_scenarios(self, tmp_path):
        """Test running multiple scenarios."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)

        scenario1 = (
            ScenarioBuilder("test1")
            .interact("agent", "Hello", "Hi!")
            .expectResponseContains("Hi")
            .build()
        )
        scenario2 = (
            ScenarioBuilder("test2")
            .interact("agent", "Goodbye", "Bye!")
            .expectResponseContains("Bye")
            .build()
        )

        tester.addScenario(scenario1)
        tester.addScenario(scenario2)

        results = tester.runAll()

        assert len(results) == 2
        assert tester.allPassed()

    def test_run_with_tags(self, tmp_path):
        """Test running scenarios filtered by tags."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)

        scenario1 = (
            ScenarioBuilder("smoke1")
            .withTags("smoke")
            .interact("agent", "Hello", "Hi!")
            .build()
        )
        scenario2 = (
            ScenarioBuilder("regression1")
            .withTags("regression")
            .interact("agent", "Hello", "Hi!")
            .build()
        )

        tester.addScenario(scenario1)
        tester.addScenario(scenario2)

        # Only run smoke tests
        results = tester.runAll(tags=["smoke"])

        assert len(results) == 1
        assert results[0].scenario == "smoke1"

    def test_generate_report(self, tmp_path):
        """Test report generation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("report_test")
            .interact("agent", "Hello", "Hi!")
            .expectResponseContains("Hi")
            .build()
        )

        tester.runScenario(scenario)
        report = tester.generateReport()

        assert "Test Suite Report" in report
        assert "report_test" in report

    def test_result_formatting(self, tmp_path):
        """Test result formatting."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("format_test")
            .interact("agent", "Hello", "Hi!")
            .expectResponseContains("Hi")
            .build()
        )

        result = tester.runScenario(scenario)
        formatted = result.format()

        assert "PASSED" in formatted
        assert "format_test" in formatted


class TestSimulationScenarioTesting:
    """Tests for scenario testing in Simulation."""

    def test_create_scenario_tester(self, tmp_path):
        """Test creating scenario tester from Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        tester = sim.createScenarioTester()
        assert tester is not None
        assert isinstance(tester, ScenarioTester)

    def test_create_scenario_tester_requires_test_mode(self, tmp_path):
        """Test that createScenarioTester requires test mode."""
        sim = Simulation(name="test", dbPath=tmp_path, testMode=False)

        with pytest.raises(Exception):  # SimulationError
            sim.createScenarioTester()

    def test_run_scenario_from_simulation(self, tmp_path):
        """Test running scenario via Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        scenario = (
            ScenarioBuilder("sim_test")
            .interact("agent", "Hello", "Hi there!")
            .expectResponseContains("Hi")
            .build()
        )

        result = sim.runScenario(scenario)

        assert result["passed"]
        assert result["scenario"] == "sim_test"

    def test_run_scenario_requires_test_mode(self, tmp_path):
        """Test that runScenario requires test mode."""
        sim = Simulation(name="test", dbPath=tmp_path, testMode=False)

        scenario = (
            ScenarioBuilder("test")
            .interact("agent", "Hello", "Hi!")
            .build()
        )

        with pytest.raises(Exception):  # SimulationError
            sim.runScenario(scenario)


class TestCallCountAssertion:
    """Tests for call count assertions."""

    def test_expect_call_count(self, tmp_path):
        """Test call count assertion."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        tester = ScenarioTester(sim)
        scenario = (
            ScenarioBuilder("call_count_test")
            .interact("agent", "Hello", "Hi!")
            .interact("agent", "Again", "Hi again!")
            .expectCallCount(2)
            .build()
        )

        result = tester.runScenario(scenario)

        assert result.passed


class TestSetupTeardown:
    """Tests for scenario setup and teardown."""

    def test_setup_callback(self, tmp_path):
        """Test setup callback execution."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        setup_called = [False]

        def setup():
            setup_called[0] = True

        scenario = (
            ScenarioBuilder("setup_test")
            .withSetup(setup)
            .interact("agent", "Hello", "Hi!")
            .build()
        )

        tester = ScenarioTester(sim)
        tester.runScenario(scenario)

        assert setup_called[0]

    def test_teardown_callback(self, tmp_path):
        """Test teardown callback execution."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)
        sim.registerAgent(AgentConfig(name="agent", role="Test", systemPrompt="You are a test"))

        teardown_called = [False]

        def teardown():
            teardown_called[0] = True

        scenario = (
            ScenarioBuilder("teardown_test")
            .withTeardown(teardown)
            .interact("agent", "Hello", "Hi!")
            .build()
        )

        tester = ScenarioTester(sim)
        tester.runScenario(scenario)

        assert teardown_called[0]
