"""Agent response validation framework.

Provides tools for validating agent responses against expected behaviors,
supporting FR41 (validate responses) and FR45 (compare configurations).
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("pm6.testing")


class ValidationLevel(str, Enum):
    """Severity levels for validation results."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a single validation check.

    Attributes:
        passed: Whether the check passed.
        rule: Name of the validation rule.
        message: Description of the result.
        level: Severity level if failed.
        actual: Actual value found.
        expected: Expected value.
    """

    passed: bool
    rule: str
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    actual: Any = None
    expected: Any = None

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "rule": self.rule,
            "message": self.message,
            "level": self.level.value,
            "actual": self.actual,
            "expected": self.expected,
        }


@dataclass
class ValidationReport:
    """Complete validation report.

    Attributes:
        agentName: Agent that was validated.
        response: Response that was validated.
        results: Individual validation results.
        passed: Overall pass/fail.
        errorCount: Number of errors.
        warningCount: Number of warnings.
    """

    agentName: str
    response: str
    results: list[ValidationResult] = field(default_factory=list)
    passed: bool = True
    errorCount: int = 0
    warningCount: int = 0

    def addResult(self, result: ValidationResult) -> None:
        """Add a validation result."""
        self.results.append(result)
        if not result.passed:
            if result.level == ValidationLevel.ERROR:
                self.errorCount += 1
                self.passed = False
            elif result.level == ValidationLevel.WARNING:
                self.warningCount += 1

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agentName": self.agentName,
            "response": self.response[:100] + "..." if len(self.response) > 100 else self.response,
            "passed": self.passed,
            "errorCount": self.errorCount,
            "warningCount": self.warningCount,
            "results": [r.toDict() for r in self.results],
        }

    def format(self) -> str:
        """Format as human-readable string."""
        lines = [
            f"Validation Report: {self.agentName}",
            f"Status: {'PASSED' if self.passed else 'FAILED'}",
            f"Errors: {self.errorCount}, Warnings: {self.warningCount}",
            "-" * 40,
        ]

        for result in self.results:
            status = "✓" if result.passed else "✗"
            lines.append(f"{status} [{result.level.value}] {result.rule}: {result.message}")

        return "\n".join(lines)


# Type for custom validators
ValidatorCallback = Callable[[str, dict[str, Any]], ValidationResult]


@dataclass
class ValidationRule:
    """A rule for validating agent responses.

    Attributes:
        name: Rule name.
        validator: Function that performs validation.
        level: Severity if rule fails.
        enabled: Whether rule is active.
    """

    name: str
    validator: Callable[[str, dict[str, Any]], bool]
    message: str = ""
    level: ValidationLevel = ValidationLevel.ERROR
    enabled: bool = True


class AgentValidator:
    """Validates agent responses against expected behaviors.

    Supports multiple validation strategies:
    - Content validation (contains, not contains)
    - Pattern validation (regex matching)
    - Length validation (min/max)
    - Custom validation functions

    Args:
        strictMode: If True, any validation failure is an error.
    """

    def __init__(self, strictMode: bool = False):
        self._strictMode = strictMode
        self._agentRules: dict[str, list[ValidationRule]] = {}
        self._globalRules: list[ValidationRule] = []

    def addRule(self, agentName: str, rule: ValidationRule) -> None:
        """Add a validation rule for an agent.

        Args:
            agentName: Agent to add rule for (or "*" for all).
            rule: The validation rule.
        """
        if agentName == "*":
            self._globalRules.append(rule)
        else:
            if agentName not in self._agentRules:
                self._agentRules[agentName] = []
            self._agentRules[agentName].append(rule)

    def addContainsCheck(
        self,
        agentName: str,
        content: str,
        caseSensitive: bool = False,
        level: ValidationLevel = ValidationLevel.ERROR,
    ) -> None:
        """Add a check that response contains specific content.

        Args:
            agentName: Agent name.
            content: Content that must be present.
            caseSensitive: Whether matching is case-sensitive.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            if caseSensitive:
                return content in response
            return content.lower() in response.lower()

        rule = ValidationRule(
            name=f"contains:{content[:20]}",
            validator=validator,
            message=f"Response must contain: '{content}'",
            level=level,
        )
        self.addRule(agentName, rule)

    def addNotContainsCheck(
        self,
        agentName: str,
        content: str,
        caseSensitive: bool = False,
        level: ValidationLevel = ValidationLevel.ERROR,
    ) -> None:
        """Add a check that response does NOT contain specific content.

        Args:
            agentName: Agent name.
            content: Content that must NOT be present.
            caseSensitive: Whether matching is case-sensitive.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            if caseSensitive:
                return content not in response
            return content.lower() not in response.lower()

        rule = ValidationRule(
            name=f"not_contains:{content[:20]}",
            validator=validator,
            message=f"Response must NOT contain: '{content}'",
            level=level,
        )
        self.addRule(agentName, rule)

    def addPatternCheck(
        self,
        agentName: str,
        pattern: str,
        mustMatch: bool = True,
        level: ValidationLevel = ValidationLevel.ERROR,
    ) -> None:
        """Add a regex pattern check.

        Args:
            agentName: Agent name.
            pattern: Regex pattern.
            mustMatch: True if pattern must match, False if must NOT match.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            try:
                match = bool(re.search(pattern, response, re.IGNORECASE))
                return match if mustMatch else not match
            except re.error:
                return False

        action = "must match" if mustMatch else "must NOT match"
        rule = ValidationRule(
            name=f"pattern:{pattern[:20]}",
            validator=validator,
            message=f"Response {action} pattern: '{pattern}'",
            level=level,
        )
        self.addRule(agentName, rule)

    def addLengthCheck(
        self,
        agentName: str,
        minLength: int | None = None,
        maxLength: int | None = None,
        level: ValidationLevel = ValidationLevel.WARNING,
    ) -> None:
        """Add a length validation check.

        Args:
            agentName: Agent name.
            minLength: Minimum response length.
            maxLength: Maximum response length.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            length = len(response)
            if minLength is not None and length < minLength:
                return False
            if maxLength is not None and length > maxLength:
                return False
            return True

        bounds = []
        if minLength is not None:
            bounds.append(f"min={minLength}")
        if maxLength is not None:
            bounds.append(f"max={maxLength}")

        rule = ValidationRule(
            name=f"length:{','.join(bounds)}",
            validator=validator,
            message=f"Response length must be {', '.join(bounds)}",
            level=level,
        )
        self.addRule(agentName, rule)

    def addWordCountCheck(
        self,
        agentName: str,
        minWords: int | None = None,
        maxWords: int | None = None,
        level: ValidationLevel = ValidationLevel.WARNING,
    ) -> None:
        """Add a word count validation check.

        Args:
            agentName: Agent name.
            minWords: Minimum word count.
            maxWords: Maximum word count.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            words = len(response.split())
            if minWords is not None and words < minWords:
                return False
            if maxWords is not None and words > maxWords:
                return False
            return True

        bounds = []
        if minWords is not None:
            bounds.append(f"min={minWords}")
        if maxWords is not None:
            bounds.append(f"max={maxWords}")

        rule = ValidationRule(
            name=f"word_count:{','.join(bounds)}",
            validator=validator,
            message=f"Word count must be {', '.join(bounds)}",
            level=level,
        )
        self.addRule(agentName, rule)

    def addCustomValidator(
        self,
        agentName: str,
        name: str,
        validator: Callable[[str, dict[str, Any]], bool],
        message: str = "",
        level: ValidationLevel = ValidationLevel.ERROR,
    ) -> None:
        """Add a custom validation function.

        Args:
            agentName: Agent name.
            name: Rule name.
            validator: Function(response, context) -> bool.
            message: Failure message.
            level: Severity if check fails.
        """
        rule = ValidationRule(
            name=name,
            validator=validator,
            message=message or f"Custom validation '{name}' failed",
            level=level,
        )
        self.addRule(agentName, rule)

    def addStateBasedCheck(
        self,
        agentName: str,
        name: str,
        stateKey: str,
        expectedValue: Any,
        level: ValidationLevel = ValidationLevel.ERROR,
    ) -> None:
        """Add validation based on world state.

        Args:
            agentName: Agent name.
            name: Rule name.
            stateKey: Key to check in context state.
            expectedValue: Expected value.
            level: Severity if check fails.
        """
        def validator(response: str, context: dict[str, Any]) -> bool:
            state = context.get("worldState", {})
            return state.get(stateKey) == expectedValue

        rule = ValidationRule(
            name=name,
            validator=validator,
            message=f"State '{stateKey}' should be {expectedValue}",
            level=level,
        )
        self.addRule(agentName, rule)

    def validate(
        self,
        agentName: str,
        response: str,
        context: dict[str, Any] | None = None,
    ) -> ValidationReport:
        """Validate an agent response.

        Args:
            agentName: Agent that produced the response.
            response: Response text to validate.
            context: Additional context (world state, input, etc.).

        Returns:
            ValidationReport with all results.
        """
        context = context or {}
        report = ValidationReport(agentName=agentName, response=response)

        # Get rules for this agent
        rules = self._globalRules + self._agentRules.get(agentName, [])

        for rule in rules:
            if not rule.enabled:
                continue

            try:
                passed = rule.validator(response, context)
                level = rule.level if self._strictMode else rule.level

                result = ValidationResult(
                    passed=passed,
                    rule=rule.name,
                    message=rule.message if not passed else "OK",
                    level=level,
                    actual=response[:50] + "..." if len(response) > 50 else response,
                    expected=rule.message,
                )
                report.addResult(result)

            except Exception as e:
                result = ValidationResult(
                    passed=False,
                    rule=rule.name,
                    message=f"Validation error: {e}",
                    level=ValidationLevel.ERROR,
                )
                report.addResult(result)

        logger.debug(f"Validated {agentName}: passed={report.passed}")
        return report

    def validateBatch(
        self,
        responses: list[tuple[str, str]],
        context: dict[str, Any] | None = None,
    ) -> list[ValidationReport]:
        """Validate multiple responses.

        Args:
            responses: List of (agentName, response) tuples.
            context: Shared context.

        Returns:
            List of validation reports.
        """
        return [self.validate(agent, resp, context) for agent, resp in responses]

    def clearRules(self, agentName: str | None = None) -> None:
        """Clear validation rules.

        Args:
            agentName: Agent to clear (None for all).
        """
        if agentName is None:
            self._agentRules.clear()
            self._globalRules.clear()
        elif agentName == "*":
            self._globalRules.clear()
        else:
            self._agentRules.pop(agentName, None)

    def hasRules(self, agentName: str) -> bool:
        """Check if agent has validation rules.

        Args:
            agentName: Agent name.

        Returns:
            True if rules exist.
        """
        if self._globalRules:
            return True
        return agentName in self._agentRules and len(self._agentRules[agentName]) > 0


@dataclass
class ComparisonResult:
    """Result of comparing agent responses.

    Attributes:
        configA: First configuration name.
        configB: Second configuration name.
        responseA: Response from config A.
        responseB: Response from config B.
        similarity: Similarity score (0.0 to 1.0).
        differences: List of differences found.
    """

    configA: str
    configB: str
    responseA: str
    responseB: str
    similarity: float
    differences: list[str] = field(default_factory=list)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "configA": self.configA,
            "configB": self.configB,
            "responseA": self.responseA[:100] + "..." if len(self.responseA) > 100 else self.responseA,
            "responseB": self.responseB[:100] + "..." if len(self.responseB) > 100 else self.responseB,
            "similarity": self.similarity,
            "differences": self.differences,
        }


class AgentComparator:
    """Compares agent behavior across different configurations.

    Supports FR45: Developer can compare agent behavior across
    different configurations.
    """

    def __init__(self):
        self._comparisons: list[ComparisonResult] = []

    def compare(
        self,
        configA: str,
        responseA: str,
        configB: str,
        responseB: str,
    ) -> ComparisonResult:
        """Compare two responses from different configurations.

        Args:
            configA: Name of first configuration.
            responseA: Response from first configuration.
            configB: Name of second configuration.
            responseB: Response from second configuration.

        Returns:
            ComparisonResult with similarity and differences.
        """
        similarity = self._calculateSimilarity(responseA, responseB)
        differences = self._findDifferences(responseA, responseB)

        result = ComparisonResult(
            configA=configA,
            configB=configB,
            responseA=responseA,
            responseB=responseB,
            similarity=similarity,
            differences=differences,
        )
        self._comparisons.append(result)
        return result

    def _calculateSimilarity(self, a: str, b: str) -> float:
        """Calculate similarity between two strings.

        Uses Jaccard similarity on word sets.
        """
        wordsA = set(a.lower().split())
        wordsB = set(b.lower().split())

        if not wordsA and not wordsB:
            return 1.0
        if not wordsA or not wordsB:
            return 0.0

        intersection = len(wordsA & wordsB)
        union = len(wordsA | wordsB)

        return intersection / union

    def _findDifferences(self, a: str, b: str) -> list[str]:
        """Find key differences between responses."""
        differences = []

        # Length difference
        lenDiff = abs(len(a) - len(b))
        if lenDiff > 100:
            differences.append(f"Length difference: {lenDiff} characters")

        # Word count difference
        wordsA = len(a.split())
        wordsB = len(b.split())
        if abs(wordsA - wordsB) > 10:
            differences.append(f"Word count difference: {abs(wordsA - wordsB)}")

        # Unique words in each
        setA = set(a.lower().split())
        setB = set(b.lower().split())
        onlyInA = setA - setB
        onlyInB = setB - setA

        if onlyInA:
            sample = list(onlyInA)[:5]
            differences.append(f"Words only in A: {', '.join(sample)}")
        if onlyInB:
            sample = list(onlyInB)[:5]
            differences.append(f"Words only in B: {', '.join(sample)}")

        return differences

    def compareMultiple(
        self,
        configs: dict[str, str],
    ) -> list[ComparisonResult]:
        """Compare multiple configurations pairwise.

        Args:
            configs: Dictionary of {configName: response}.

        Returns:
            List of pairwise comparison results.
        """
        results = []
        configNames = list(configs.keys())

        for i, nameA in enumerate(configNames):
            for nameB in configNames[i + 1:]:
                result = self.compare(
                    nameA, configs[nameA],
                    nameB, configs[nameB],
                )
                results.append(result)

        return results

    def getHistory(self) -> list[ComparisonResult]:
        """Get comparison history."""
        return self._comparisons.copy()

    def clearHistory(self) -> None:
        """Clear comparison history."""
        self._comparisons.clear()

    def generateReport(self) -> str:
        """Generate a human-readable comparison report."""
        if not self._comparisons:
            return "No comparisons recorded."

        lines = ["Agent Comparison Report", "=" * 40]

        for i, result in enumerate(self._comparisons, 1):
            lines.append(f"\n{i}. {result.configA} vs {result.configB}")
            lines.append(f"   Similarity: {result.similarity:.2%}")
            if result.differences:
                lines.append("   Differences:")
                for diff in result.differences:
                    lines.append(f"     - {diff}")

        return "\n".join(lines)
