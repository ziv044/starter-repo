"""Automated scenario testing framework.

Provides tools for defining and running automated test suites
against simulation scenarios, supporting FR47.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pm6.testing.mockClient import MockAnthropicClient, MockResponse

logger = logging.getLogger("pm6.testing")


class AssertionType(str, Enum):
    """Types of test assertions."""

    STATE_EQUALS = "state_equals"
    STATE_CONTAINS = "state_contains"
    RESPONSE_CONTAINS = "response_contains"
    RESPONSE_PATTERN = "response_pattern"
    CALL_COUNT = "call_count"
    CUSTOM = "custom"


@dataclass
class ScenarioAssertion:
    """A single test assertion.

    Attributes:
        type: Type of assertion.
        key: Key or identifier for the assertion.
        expected: Expected value.
        message: Custom failure message.
    """

    type: AssertionType
    key: str
    expected: Any
    message: str = ""


# Alias for backwards compatibility
TestAssertion = ScenarioAssertion
TestAssertion.__test__ = False  # Tell pytest not to collect this


@dataclass
class ScenarioStep:
    """A single step in a test scenario.

    Attributes:
        action: Action to perform (interact, setState, etc.).
        agentName: Agent to interact with (if applicable).
        userInput: User input for interaction.
        mockResponse: Mock response to return.
        assertions: Assertions to check after this step.
        description: Human-readable description.
    """

    action: str = "interact"
    agentName: str = ""
    userInput: str = ""
    mockResponse: str | MockResponse = ""
    assertions: list[ScenarioAssertion] = field(default_factory=list)
    description: str = ""


# Alias for backwards compatibility
TestStep = ScenarioStep
TestStep.__test__ = False  # Tell pytest not to collect this


@dataclass
class AssertionResult:
    """Result of a single assertion.

    Attributes:
        passed: Whether the assertion passed.
        assertion: The assertion that was tested.
        actual: Actual value found.
        message: Result message.
    """

    passed: bool
    assertion: ScenarioAssertion
    actual: Any = None
    message: str = ""

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "type": self.assertion.type.value,
            "key": self.assertion.key,
            "expected": self.assertion.expected,
            "actual": self.actual,
            "message": self.message,
        }


# Alias for backwards compatibility
TestResult = AssertionResult
TestResult.__test__ = False  # Tell pytest not to collect this


@dataclass
class StepResult:
    """Result of executing a test step.

    Attributes:
        step: The step that was executed.
        passed: Whether all assertions passed.
        response: Response received (if any).
        assertionResults: Results of individual assertions.
        error: Error message if step failed.
    """

    step: ScenarioStep
    passed: bool = True
    response: str = ""
    assertionResults: list[AssertionResult] = field(default_factory=list)
    error: str = ""

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.step.action,
            "description": self.step.description,
            "passed": self.passed,
            "response": self.response[:100] + "..." if len(self.response) > 100 else self.response,
            "assertionResults": [r.toDict() for r in self.assertionResults],
            "error": self.error,
        }


@dataclass
class ScenarioResult:
    """Result of running a complete test scenario.

    Attributes:
        scenario: Name of the scenario.
        passed: Overall pass/fail.
        stepResults: Results of each step.
        totalAssertions: Total assertions checked.
        passedAssertions: Assertions that passed.
        duration: Time taken in seconds.
    """

    scenario: str
    passed: bool = True
    stepResults: list[StepResult] = field(default_factory=list)
    totalAssertions: int = 0
    passedAssertions: int = 0
    duration: float = 0.0

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "stepResults": [r.toDict() for r in self.stepResults],
            "totalAssertions": self.totalAssertions,
            "passedAssertions": self.passedAssertions,
            "duration": self.duration,
        }

    def format(self) -> str:
        """Format as human-readable string."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"Scenario: {self.scenario}",
            f"Status: {status}",
            f"Assertions: {self.passedAssertions}/{self.totalAssertions} passed",
            f"Duration: {self.duration:.2f}s",
            "-" * 40,
        ]

        for i, step in enumerate(self.stepResults, 1):
            stepStatus = "✓" if step.passed else "✗"
            lines.append(f"{stepStatus} Step {i}: {step.step.description or step.step.action}")
            if step.error:
                lines.append(f"   Error: {step.error}")
            for result in step.assertionResults:
                status = "✓" if result.passed else "✗"
                lines.append(f"   {status} {result.assertion.key}: {result.message}")

        return "\n".join(lines)


@dataclass
class TestScenario:
    """A complete test scenario.

    Attributes:
        name: Scenario name.
        description: What the scenario tests.
        steps: Test steps to execute.
        initialState: Initial world state.
        setup: Setup callback before running.
        teardown: Teardown callback after running.
        tags: Tags for filtering scenarios.
    """

    name: str
    description: str = ""
    steps: list[TestStep] = field(default_factory=list)
    initialState: dict[str, Any] = field(default_factory=dict)
    setup: Callable[[], None] | None = None
    teardown: Callable[[], None] | None = None
    tags: list[str] = field(default_factory=list)


TestScenario.__test__ = False  # Tell pytest not to collect this


class ScenarioBuilder:
    """Fluent builder for test scenarios."""

    def __init__(self, name: str):
        self._name = name
        self._description = ""
        self._steps: list[TestStep] = []
        self._initialState: dict[str, Any] = {}
        self._setup: Callable[[], None] | None = None
        self._teardown: Callable[[], None] | None = None
        self._tags: list[str] = []
        self._currentStep: TestStep | None = None

    def describe(self, description: str) -> "ScenarioBuilder":
        """Set scenario description."""
        self._description = description
        return self

    def withState(self, state: dict[str, Any]) -> "ScenarioBuilder":
        """Set initial world state."""
        self._initialState = state
        return self

    def withSetup(self, callback: Callable[[], None]) -> "ScenarioBuilder":
        """Set setup callback."""
        self._setup = callback
        return self

    def withTeardown(self, callback: Callable[[], None]) -> "ScenarioBuilder":
        """Set teardown callback."""
        self._teardown = callback
        return self

    def withTags(self, *tags: str) -> "ScenarioBuilder":
        """Add tags."""
        self._tags.extend(tags)
        return self

    def interact(
        self,
        agentName: str,
        userInput: str,
        mockResponse: str | MockResponse = "",
        description: str = "",
    ) -> "ScenarioBuilder":
        """Add an interaction step."""
        self._finishCurrentStep()
        self._currentStep = TestStep(
            action="interact",
            agentName=agentName,
            userInput=userInput,
            mockResponse=mockResponse,
            description=description or f"Interact with {agentName}",
        )
        return self

    def setState(
        self,
        state: dict[str, Any],
        description: str = "",
    ) -> "ScenarioBuilder":
        """Add a setState step."""
        self._finishCurrentStep()
        self._currentStep = TestStep(
            action="setState",
            mockResponse=str(state),  # Store state as string for reference
            description=description or "Set world state",
        )
        self._currentStep._stateToSet = state  # type: ignore
        return self

    def wait(
        self,
        description: str = "",
    ) -> "ScenarioBuilder":
        """Add a wait/pause step (for manual assertions)."""
        self._finishCurrentStep()
        self._currentStep = TestStep(
            action="wait",
            description=description or "Wait step",
        )
        return self

    def expectState(self, key: str, value: Any, message: str = "") -> "ScenarioBuilder":
        """Assert world state equals value."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.STATE_EQUALS,
                key=key,
                expected=value,
                message=message,
            )
        )
        return self

    def expectStateContains(self, key: str, value: Any, message: str = "") -> "ScenarioBuilder":
        """Assert world state contains value."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.STATE_CONTAINS,
                key=key,
                expected=value,
                message=message,
            )
        )
        return self

    def expectResponseContains(self, content: str, message: str = "") -> "ScenarioBuilder":
        """Assert response contains content."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.RESPONSE_CONTAINS,
                key="response",
                expected=content,
                message=message,
            )
        )
        return self

    def expectResponseMatches(self, pattern: str, message: str = "") -> "ScenarioBuilder":
        """Assert response matches regex pattern."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.RESPONSE_PATTERN,
                key="response",
                expected=pattern,
                message=message,
            )
        )
        return self

    def expectCallCount(self, count: int, message: str = "") -> "ScenarioBuilder":
        """Assert total LLM call count."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.CALL_COUNT,
                key="callCount",
                expected=count,
                message=message,
            )
        )
        return self

    def expectCustom(
        self,
        name: str,
        checker: Callable[[Any], bool],
        expected: Any = True,
        message: str = "",
    ) -> "ScenarioBuilder":
        """Add a custom assertion."""
        if self._currentStep is None:
            raise ValueError("No current step to add assertion to")
        self._currentStep.assertions.append(
            TestAssertion(
                type=AssertionType.CUSTOM,
                key=name,
                expected={"checker": checker, "value": expected},
                message=message,
            )
        )
        return self

    def _finishCurrentStep(self) -> None:
        """Finish and add current step to list."""
        if self._currentStep is not None:
            self._steps.append(self._currentStep)
            self._currentStep = None

    def build(self) -> TestScenario:
        """Build the test scenario."""
        self._finishCurrentStep()
        return TestScenario(
            name=self._name,
            description=self._description,
            steps=self._steps,
            initialState=self._initialState,
            setup=self._setup,
            teardown=self._teardown,
            tags=self._tags,
        )


class ScenarioTester:
    """Runs automated test scenarios against simulations.

    Args:
        simulation: Simulation to test (must be in test mode).
    """

    def __init__(self, simulation: Any):
        self._simulation = simulation
        self._scenarios: list[TestScenario] = []
        self._results: list[ScenarioResult] = []

    def addScenario(self, scenario: TestScenario) -> None:
        """Add a test scenario.

        Args:
            scenario: Scenario to add.
        """
        self._scenarios.append(scenario)

    def createScenario(self, name: str) -> ScenarioBuilder:
        """Create a new scenario using the builder.

        Args:
            name: Scenario name.

        Returns:
            ScenarioBuilder for fluent construction.
        """
        return ScenarioBuilder(name)

    def runScenario(self, scenario: TestScenario) -> ScenarioResult:
        """Run a single test scenario.

        Args:
            scenario: Scenario to run.

        Returns:
            ScenarioResult with test results.
        """
        import re
        import time

        startTime = time.time()
        result = ScenarioResult(scenario=scenario.name)

        try:
            # Run setup
            if scenario.setup:
                scenario.setup()

            # Set initial state
            if scenario.initialState:
                self._simulation.setWorldState(scenario.initialState)

            # Run each step
            for step in scenario.steps:
                stepResult = self._runStep(step)
                result.stepResults.append(stepResult)

                # Update counts
                for assertResult in stepResult.assertionResults:
                    result.totalAssertions += 1
                    if assertResult.passed:
                        result.passedAssertions += 1
                    else:
                        result.passed = False

                # Stop on step failure if it has error
                if stepResult.error:
                    result.passed = False
                    break

        except Exception as e:
            result.passed = False
            logger.error(f"Scenario '{scenario.name}' failed: {e}")

        finally:
            # Run teardown
            if scenario.teardown:
                try:
                    scenario.teardown()
                except Exception as e:
                    logger.warning(f"Teardown failed: {e}")

            result.duration = time.time() - startTime

        self._results.append(result)
        return result

    def _runStep(self, step: TestStep) -> StepResult:
        """Run a single test step.

        Args:
            step: Step to run.

        Returns:
            StepResult with step results.
        """
        import re

        stepResult = StepResult(step=step)

        try:
            # Execute the action
            if step.action == "interact":
                # Add mock response if provided
                if step.mockResponse:
                    self._simulation.addMockResponse(step.mockResponse)

                # Perform interaction
                response = self._simulation.interact(step.agentName, step.userInput)
                stepResult.response = response.content

            elif step.action == "setState":
                stateToSet = getattr(step, "_stateToSet", {})
                self._simulation.setWorldState(stateToSet)

            elif step.action == "wait":
                pass  # No action needed

            # Run assertions
            for assertion in step.assertions:
                assertResult = self._checkAssertion(assertion, stepResult.response)
                stepResult.assertionResults.append(assertResult)
                if not assertResult.passed:
                    stepResult.passed = False

        except Exception as e:
            stepResult.error = str(e)
            stepResult.passed = False

        return stepResult

    def _checkAssertion(self, assertion: TestAssertion, response: str) -> TestResult:
        """Check a single assertion.

        Args:
            assertion: Assertion to check.
            response: Current response text.

        Returns:
            TestResult for this assertion.
        """
        import re

        result = TestResult(assertion=assertion, passed=False)

        try:
            if assertion.type == AssertionType.STATE_EQUALS:
                actual = self._simulation.getWorldState().get(assertion.key)
                result.actual = actual
                result.passed = actual == assertion.expected
                result.message = f"Expected {assertion.expected}, got {actual}"

            elif assertion.type == AssertionType.STATE_CONTAINS:
                state = self._simulation.getWorldState()
                actual = state.get(assertion.key)
                result.actual = actual
                if isinstance(actual, (list, tuple)):
                    result.passed = assertion.expected in actual
                elif isinstance(actual, dict):
                    result.passed = assertion.expected in actual.values()
                elif isinstance(actual, str):
                    result.passed = assertion.expected in actual
                else:
                    result.passed = False
                result.message = f"Expected to contain {assertion.expected}"

            elif assertion.type == AssertionType.RESPONSE_CONTAINS:
                result.actual = response[:50] + "..." if len(response) > 50 else response
                result.passed = assertion.expected.lower() in response.lower()
                result.message = f"Expected response to contain '{assertion.expected}'"

            elif assertion.type == AssertionType.RESPONSE_PATTERN:
                result.actual = response[:50] + "..." if len(response) > 50 else response
                result.passed = bool(re.search(assertion.expected, response, re.IGNORECASE))
                result.message = f"Expected response to match '{assertion.expected}'"

            elif assertion.type == AssertionType.CALL_COUNT:
                actual = self._simulation._llmClient.callCount
                result.actual = actual
                result.passed = actual == assertion.expected
                result.message = f"Expected {assertion.expected} calls, got {actual}"

            elif assertion.type == AssertionType.CUSTOM:
                checker = assertion.expected.get("checker")
                expectedValue = assertion.expected.get("value")
                actualValue = checker(self._simulation)
                result.actual = actualValue
                result.passed = actualValue == expectedValue
                result.message = assertion.message or f"Custom check: {assertion.key}"

            if result.passed:
                result.message = "OK"

        except Exception as e:
            result.message = f"Assertion error: {e}"

        return result

    def runAll(self, tags: list[str] | None = None) -> list[ScenarioResult]:
        """Run all registered scenarios.

        Args:
            tags: Only run scenarios with these tags (None for all).

        Returns:
            List of scenario results.
        """
        results = []

        for scenario in self._scenarios:
            # Filter by tags if specified
            if tags:
                if not any(t in scenario.tags for t in tags):
                    continue

            result = self.runScenario(scenario)
            results.append(result)

        return results

    def getResults(self) -> list[ScenarioResult]:
        """Get all test results."""
        return self._results.copy()

    def clearResults(self) -> None:
        """Clear test results."""
        self._results.clear()

    def generateReport(self) -> str:
        """Generate a human-readable test report."""
        if not self._results:
            return "No test results."

        passed = sum(1 for r in self._results if r.passed)
        total = len(self._results)

        lines = [
            "Test Suite Report",
            "=" * 40,
            f"Scenarios: {passed}/{total} passed",
            "",
        ]

        for result in self._results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"[{status}] {result.scenario}")
            lines.append(f"       Assertions: {result.passedAssertions}/{result.totalAssertions}")

        return "\n".join(lines)

    def allPassed(self) -> bool:
        """Check if all scenarios passed."""
        return all(r.passed for r in self._results)
