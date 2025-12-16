"""Testing utilities for pm6.

Provides mock clients, validators, and test helpers for deterministic testing.
"""

from pm6.testing.mockClient import (
    MockAnthropicClient,
    MockResponse,
    MockResponseHandler,
)
from pm6.testing.scenarioTester import (
    AssertionResult,
    AssertionType,
    ScenarioAssertion,
    ScenarioBuilder,
    ScenarioResult,
    ScenarioStep,
    ScenarioTester,
    StepResult,
    TestAssertion,
    TestResult,
    TestScenario,
    TestStep,
)
from pm6.testing.validator import (
    AgentComparator,
    AgentValidator,
    ComparisonResult,
    ValidationLevel,
    ValidationReport,
    ValidationResult,
    ValidationRule,
)

__all__ = [
    # Mock client
    "MockAnthropicClient",
    "MockResponse",
    "MockResponseHandler",
    # Validator
    "AgentValidator",
    "AgentComparator",
    "ValidationRule",
    "ValidationResult",
    "ValidationReport",
    "ValidationLevel",
    "ComparisonResult",
    # Scenario tester - new names
    "ScenarioTester",
    "ScenarioBuilder",
    "ScenarioAssertion",
    "ScenarioStep",
    "ScenarioResult",
    "AssertionResult",
    "StepResult",
    "AssertionType",
    # Scenario tester - legacy aliases (backwards compatibility)
    "TestScenario",
    "TestStep",
    "TestAssertion",
    "TestResult",
]
