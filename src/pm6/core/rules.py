"""Simulation rules and constraints.

Defines rules that govern simulation behavior, including:
- State validation rules
- Interaction constraints
- Turn limits
- Agent availability rules
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("pm6.core")


class RuleType(str, Enum):
    """Types of simulation rules."""

    STATE_VALIDATION = "state_validation"
    INTERACTION_CONSTRAINT = "interaction_constraint"
    TURN_LIMIT = "turn_limit"
    AGENT_AVAILABILITY = "agent_availability"
    CUSTOM = "custom"


@dataclass
class Rule:
    """A simulation rule.

    Attributes:
        name: Rule name.
        ruleType: Type of rule.
        condition: Function that evaluates the rule.
        message: Message when rule is violated.
        enabled: Whether rule is active.
    """

    name: str
    ruleType: RuleType
    condition: Callable[[dict[str, Any]], bool]
    message: str = ""
    enabled: bool = True

    def evaluate(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate the rule.

        Args:
            context: Context dict with state, agent, etc.

        Returns:
            Tuple of (passed, message).
        """
        if not self.enabled:
            return True, ""

        try:
            passed = self.condition(context)
            return passed, "" if passed else self.message
        except Exception as e:
            logger.warning(f"Rule '{self.name}' evaluation failed: {e}")
            return True, ""  # Fail open


@dataclass
class RuleViolation:
    """A rule violation.

    Attributes:
        ruleName: Name of violated rule.
        ruleType: Type of rule.
        message: Violation message.
        context: Context at time of violation.
    """

    ruleName: str
    ruleType: RuleType
    message: str
    context: dict[str, Any] = field(default_factory=dict)


class SimulationRules:
    """Manages simulation rules and constraints.

    Args:
        strictMode: If True, violations raise exceptions.
    """

    def __init__(self, strictMode: bool = False):
        self._rules: list[Rule] = []
        self._strictMode = strictMode
        self._violations: list[RuleViolation] = []

    def addRule(self, rule: Rule) -> None:
        """Add a rule.

        Args:
            rule: Rule to add.
        """
        self._rules.append(rule)
        logger.debug(f"Added rule: {rule.name}")

    def addStateValidation(
        self,
        name: str,
        condition: Callable[[dict[str, Any]], bool],
        message: str = "",
    ) -> None:
        """Add a state validation rule.

        Args:
            name: Rule name.
            condition: Function taking state dict, returns True if valid.
            message: Message when invalid.
        """
        rule = Rule(
            name=name,
            ruleType=RuleType.STATE_VALIDATION,
            condition=lambda ctx: condition(ctx.get("state", {})),
            message=message or f"State validation failed: {name}",
        )
        self.addRule(rule)

    def addInteractionConstraint(
        self,
        name: str,
        condition: Callable[[dict[str, Any]], bool],
        message: str = "",
    ) -> None:
        """Add an interaction constraint.

        Args:
            name: Rule name.
            condition: Function taking context, returns True if allowed.
            message: Message when not allowed.
        """
        rule = Rule(
            name=name,
            ruleType=RuleType.INTERACTION_CONSTRAINT,
            condition=condition,
            message=message or f"Interaction not allowed: {name}",
        )
        self.addRule(rule)

    def addTurnLimit(self, maxTurns: int, message: str = "") -> None:
        """Add a turn limit rule.

        Args:
            maxTurns: Maximum number of turns.
            message: Message when limit reached.
        """
        rule = Rule(
            name="turn_limit",
            ruleType=RuleType.TURN_LIMIT,
            condition=lambda ctx: ctx.get("turnCount", 0) < maxTurns,
            message=message or f"Turn limit reached ({maxTurns})",
        )
        self.addRule(rule)

    def addAgentAvailability(
        self,
        agentName: str,
        condition: Callable[[dict[str, Any]], bool],
        message: str = "",
    ) -> None:
        """Add an agent availability rule.

        Args:
            agentName: Agent this rule applies to.
            condition: Function taking context, returns True if available.
            message: Message when unavailable.
        """
        rule = Rule(
            name=f"agent_availability_{agentName}",
            ruleType=RuleType.AGENT_AVAILABILITY,
            condition=lambda ctx: (
                ctx.get("agentName") != agentName or condition(ctx)
            ),
            message=message or f"Agent '{agentName}' is not available",
        )
        self.addRule(rule)

    def check(
        self, context: dict[str, Any], ruleTypes: list[RuleType] | None = None
    ) -> list[RuleViolation]:
        """Check all rules against context.

        Args:
            context: Context dict with state, agent, etc.
            ruleTypes: Optional filter for rule types.

        Returns:
            List of violations.
        """
        violations: list[RuleViolation] = []

        for rule in self._rules:
            if ruleTypes and rule.ruleType not in ruleTypes:
                continue

            passed, message = rule.evaluate(context)
            if not passed:
                violation = RuleViolation(
                    ruleName=rule.name,
                    ruleType=rule.ruleType,
                    message=message,
                    context=context.copy(),
                )
                violations.append(violation)
                self._violations.append(violation)
                logger.warning(f"Rule violation: {rule.name} - {message}")

        return violations

    def checkStateValidation(self, state: dict[str, Any]) -> list[RuleViolation]:
        """Check state validation rules.

        Args:
            state: World state to validate.

        Returns:
            List of violations.
        """
        return self.check({"state": state}, [RuleType.STATE_VALIDATION])

    def checkInteraction(
        self,
        agentName: str,
        userInput: str,
        state: dict[str, Any],
        turnCount: int = 0,
    ) -> list[RuleViolation]:
        """Check rules before an interaction.

        Args:
            agentName: Agent being interacted with.
            userInput: User's input.
            state: Current world state.
            turnCount: Current turn number.

        Returns:
            List of violations.
        """
        context = {
            "agentName": agentName,
            "userInput": userInput,
            "state": state,
            "turnCount": turnCount,
        }
        return self.check(context)

    def enableRule(self, name: str) -> None:
        """Enable a rule by name."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = True
                return

    def disableRule(self, name: str) -> None:
        """Disable a rule by name."""
        for rule in self._rules:
            if rule.name == name:
                rule.enabled = False
                return

    def removeRule(self, name: str) -> None:
        """Remove a rule by name."""
        self._rules = [r for r in self._rules if r.name != name]

    def clearRules(self) -> None:
        """Remove all rules."""
        self._rules.clear()

    def getViolations(self) -> list[RuleViolation]:
        """Get all recorded violations."""
        return self._violations.copy()

    def clearViolations(self) -> None:
        """Clear recorded violations."""
        self._violations.clear()

    def listRules(self) -> list[dict[str, Any]]:
        """List all rules.

        Returns:
            List of rule info dicts.
        """
        return [
            {
                "name": r.name,
                "type": r.ruleType.value,
                "enabled": r.enabled,
                "message": r.message,
            }
            for r in self._rules
        ]

    @property
    def strictMode(self) -> bool:
        """Get strict mode setting."""
        return self._strictMode

    @strictMode.setter
    def strictMode(self, value: bool) -> None:
        """Set strict mode."""
        self._strictMode = value
