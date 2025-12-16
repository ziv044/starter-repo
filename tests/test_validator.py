"""Tests for agent validation framework."""

import pytest

from pm6.agents import AgentConfig
from pm6.core import Simulation
from pm6.testing import (
    AgentComparator,
    AgentValidator,
    ValidationLevel,
    ValidationReport,
)


class TestAgentValidator:
    """Tests for AgentValidator."""

    def test_contains_check_pass(self):
        """Test contains check that passes."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "hello")

        report = validator.validate("agent", "Hello world!")
        assert report.passed

    def test_contains_check_fail(self):
        """Test contains check that fails."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "goodbye")

        report = validator.validate("agent", "Hello world!")
        assert not report.passed
        assert report.errorCount == 1

    def test_not_contains_check(self):
        """Test not contains check."""
        validator = AgentValidator()
        validator.addNotContainsCheck("agent", "error")

        report = validator.validate("agent", "All is well!")
        assert report.passed

        report = validator.validate("agent", "Error occurred!")
        assert not report.passed

    def test_case_sensitive_check(self):
        """Test case-sensitive checking."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "Hello", caseSensitive=True)

        report = validator.validate("agent", "Hello world!")
        assert report.passed

        report = validator.validate("agent", "hello world!")
        assert not report.passed

    def test_pattern_check(self):
        """Test regex pattern validation."""
        validator = AgentValidator()
        validator.addPatternCheck("agent", r"\d{3}-\d{4}")

        report = validator.validate("agent", "Call me at 555-1234")
        assert report.passed

        report = validator.validate("agent", "No phone here")
        assert not report.passed

    def test_pattern_must_not_match(self):
        """Test pattern that must NOT match."""
        validator = AgentValidator()
        validator.addPatternCheck("agent", r"password|secret", mustMatch=False)

        report = validator.validate("agent", "Here is your data")
        assert report.passed

        report = validator.validate("agent", "The password is 123")
        assert not report.passed

    def test_length_check(self):
        """Test length validation."""
        validator = AgentValidator()
        validator.addLengthCheck("agent", minLength=10, maxLength=100, level=ValidationLevel.ERROR)

        report = validator.validate("agent", "This is a valid response!")
        assert report.passed

        report = validator.validate("agent", "Short")
        assert not report.passed

    def test_word_count_check(self):
        """Test word count validation."""
        validator = AgentValidator()
        validator.addWordCountCheck("agent", minWords=5, maxWords=20, level=ValidationLevel.ERROR)

        report = validator.validate("agent", "One two three four five six")
        assert report.passed

        report = validator.validate("agent", "Too short")
        assert not report.passed

    def test_custom_validator(self):
        """Test custom validation function."""
        validator = AgentValidator()
        validator.addCustomValidator(
            "agent",
            "starts_with_greeting",
            lambda resp, ctx: resp.lower().startswith(("hello", "hi", "greetings")),
            message="Response should start with a greeting",
        )

        report = validator.validate("agent", "Hello! How can I help?")
        assert report.passed

        report = validator.validate("agent", "What do you want?")
        assert not report.passed

    def test_state_based_check(self):
        """Test state-based validation."""
        validator = AgentValidator()
        validator.addStateBasedCheck("agent", "mood_check", "mood", "happy")

        context = {"worldState": {"mood": "happy"}}
        report = validator.validate("agent", "Any response", context)
        assert report.passed

        context = {"worldState": {"mood": "sad"}}
        report = validator.validate("agent", "Any response", context)
        assert not report.passed

    def test_warning_level(self):
        """Test warning-level validation."""
        validator = AgentValidator()
        validator.addLengthCheck("agent", minLength=100, level=ValidationLevel.WARNING)

        report = validator.validate("agent", "Short response")
        assert report.passed  # Warnings don't fail
        assert report.warningCount == 1

    def test_global_rules(self):
        """Test global rules applied to all agents."""
        validator = AgentValidator()
        validator.addNotContainsCheck("*", "confidential")

        report = validator.validate("any_agent", "This is confidential data")
        assert not report.passed

    def test_multiple_rules(self):
        """Test multiple validation rules."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "thank")
        validator.addLengthCheck("agent", minLength=10)
        validator.addPatternCheck("agent", r"[.!?]$")

        report = validator.validate("agent", "Thank you for your question!")
        assert report.passed
        assert len(report.results) == 3

    def test_validate_batch(self):
        """Test batch validation."""
        validator = AgentValidator()
        validator.addContainsCheck("agent1", "hello")
        validator.addContainsCheck("agent2", "goodbye")

        responses = [
            ("agent1", "Hello there!"),
            ("agent2", "Goodbye now!"),
        ]
        reports = validator.validateBatch(responses)

        assert len(reports) == 2
        assert all(r.passed for r in reports)

    def test_report_formatting(self):
        """Test validation report formatting."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "required")

        report = validator.validate("agent", "Missing the word")
        formatted = report.format()

        assert "FAILED" in formatted
        assert "agent" in formatted

    def test_clear_rules(self):
        """Test clearing validation rules."""
        validator = AgentValidator()
        validator.addContainsCheck("agent", "test")

        assert validator.hasRules("agent")

        validator.clearRules("agent")

        assert not validator.hasRules("agent")


class TestAgentComparator:
    """Tests for AgentComparator."""

    def test_compare_similar_responses(self):
        """Test comparing similar responses."""
        comparator = AgentComparator()

        result = comparator.compare(
            "config_a", "The weather today is sunny and warm.",
            "config_b", "Today the weather is warm and sunny.",
        )

        assert result.similarity > 0.5

    def test_compare_different_responses(self):
        """Test comparing different responses."""
        comparator = AgentComparator()

        result = comparator.compare(
            "config_a", "The budget proposal is approved.",
            "config_b", "Let's discuss the weather forecast.",
        )

        assert result.similarity < 0.5
        assert len(result.differences) > 0

    def test_compare_identical_responses(self):
        """Test comparing identical responses."""
        comparator = AgentComparator()

        result = comparator.compare(
            "config_a", "Exactly the same response.",
            "config_b", "Exactly the same response.",
        )

        assert result.similarity == 1.0

    def test_compare_multiple(self):
        """Test comparing multiple configurations."""
        comparator = AgentComparator()

        configs = {
            "gpt4": "The answer is 42.",
            "claude": "I believe the answer is 42.",
            "llama": "42 is the answer you seek.",
        }

        results = comparator.compareMultiple(configs)

        assert len(results) == 3  # 3 pairwise comparisons

    def test_generate_report(self):
        """Test report generation."""
        comparator = AgentComparator()

        comparator.compare("a", "Response A", "b", "Response B")
        comparator.compare("a", "Response A", "c", "Response C")

        report = comparator.generateReport()

        assert "Comparison Report" in report
        assert "a vs b" in report

    def test_comparison_history(self):
        """Test comparison history tracking."""
        comparator = AgentComparator()

        comparator.compare("a", "R1", "b", "R2")
        comparator.compare("c", "R3", "d", "R4")

        history = comparator.getHistory()
        assert len(history) == 2

        comparator.clearHistory()
        assert len(comparator.getHistory()) == 0


class TestSimulationValidation:
    """Tests for validation in Simulation."""

    def test_create_validator(self, tmp_path):
        """Test creating a validator from Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        validator = sim.createValidator()
        assert validator is not None
        assert isinstance(validator, AgentValidator)

    def test_validate_response(self, tmp_path):
        """Test validating a response via Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        validator = sim.createValidator()
        validator.addContainsCheck("test", "hello")

        report = sim.validateResponse("test", "Hello world!", validator)
        assert report.passed

    def test_validate_with_world_state(self, tmp_path):
        """Test validation includes world state."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            worldState={"mode": "friendly"},
        )

        validator = sim.createValidator()
        validator.addStateBasedCheck("test", "mode_check", "mode", "friendly")

        report = sim.validateResponse("test", "Any response", validator)
        assert report.passed

    def test_create_comparator(self, tmp_path):
        """Test creating a comparator from Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        comparator = sim.createComparator()
        assert comparator is not None
        assert isinstance(comparator, AgentComparator)

    def test_compare_responses(self, tmp_path):
        """Test comparing responses via Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        result = sim.compareResponses(
            "config_a", "The answer is yes.",
            "config_b", "Yes, the answer is affirmative.",
        )

        assert "similarity" in result
        assert result["similarity"] > 0
