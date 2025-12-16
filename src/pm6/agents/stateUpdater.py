"""State update system for agent interactions.

Allows agents to update simulation state based on interactions.
Supports rule-based updates, extracted values, and callbacks.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("pm6.agents")


class UpdateTrigger(str, Enum):
    """When to trigger state updates."""

    ALWAYS = "always"  # Update after every interaction
    PATTERN = "pattern"  # Update when response matches pattern
    KEYWORD = "keyword"  # Update when response contains keyword
    CONDITION = "condition"  # Update when condition is met


@dataclass
class StateUpdate:
    """A single state update to apply.

    Attributes:
        key: State key to update.
        value: New value (or callable to compute it).
        operation: How to apply the update.
    """

    key: str
    value: Any
    operation: str = "set"  # set, increment, append, merge


@dataclass
class UpdateRule:
    """A rule for updating state after interactions.

    Attributes:
        agentName: Agent this rule applies to.
        trigger: When to trigger the update.
        triggerValue: Trigger-specific value.
        updates: List of updates to apply.
        description: Human-readable description.
    """

    agentName: str
    trigger: UpdateTrigger
    triggerValue: Any = None
    updates: list[StateUpdate] = field(default_factory=list)
    description: str = ""


# Callback type for dynamic updates
StateUpdateCallback = Callable[
    [str, str, str, dict[str, Any]],  # agentName, userInput, response, currentState
    dict[str, Any],  # updates to apply
]


class AgentStateUpdater:
    """Manages state updates from agent interactions.

    Allows defining rules for how agents update simulation state.

    Args:
        autoApply: Automatically apply updates after interactions.
    """

    def __init__(self, autoApply: bool = True):
        self._autoApply = autoApply
        self._rules: dict[str, list[UpdateRule]] = {}
        self._callbacks: dict[str, StateUpdateCallback] = {}
        self._pendingUpdates: list[dict[str, Any]] = []

    def addRule(self, rule: UpdateRule) -> None:
        """Add an update rule.

        Args:
            rule: The update rule to add.
        """
        if rule.agentName not in self._rules:
            self._rules[rule.agentName] = []
        self._rules[rule.agentName].append(rule)

    def addAlwaysUpdate(
        self,
        agentName: str,
        key: str,
        value: Any,
        operation: str = "set",
    ) -> None:
        """Add an update that always triggers.

        Args:
            agentName: Agent name.
            key: State key to update.
            value: Value to set/apply.
            operation: Update operation (set, increment, append, merge).
        """
        rule = UpdateRule(
            agentName=agentName,
            trigger=UpdateTrigger.ALWAYS,
            updates=[StateUpdate(key=key, value=value, operation=operation)],
            description=f"Always {operation} {key}",
        )
        self.addRule(rule)

    def addPatternUpdate(
        self,
        agentName: str,
        pattern: str,
        key: str,
        value: Any,
        operation: str = "set",
    ) -> None:
        """Add an update triggered by response pattern.

        Args:
            agentName: Agent name.
            pattern: Regex pattern to match in response.
            key: State key to update.
            value: Value to set/apply.
            operation: Update operation.
        """
        rule = UpdateRule(
            agentName=agentName,
            trigger=UpdateTrigger.PATTERN,
            triggerValue=pattern,
            updates=[StateUpdate(key=key, value=value, operation=operation)],
            description=f"On pattern '{pattern}': {operation} {key}",
        )
        self.addRule(rule)

    def addKeywordUpdate(
        self,
        agentName: str,
        keywords: list[str],
        key: str,
        value: Any,
        operation: str = "set",
    ) -> None:
        """Add an update triggered by keywords in response.

        Args:
            agentName: Agent name.
            keywords: Keywords to match.
            key: State key to update.
            value: Value to set/apply.
            operation: Update operation.
        """
        rule = UpdateRule(
            agentName=agentName,
            trigger=UpdateTrigger.KEYWORD,
            triggerValue=keywords,
            updates=[StateUpdate(key=key, value=value, operation=operation)],
            description=f"On keywords {keywords}: {operation} {key}",
        )
        self.addRule(rule)

    def addConditionalUpdate(
        self,
        agentName: str,
        condition: Callable[[str, str, dict[str, Any]], bool],
        key: str,
        value: Any,
        operation: str = "set",
        description: str = "",
    ) -> None:
        """Add a conditional update.

        Args:
            agentName: Agent name.
            condition: Function(userInput, response, state) -> bool.
            key: State key to update.
            value: Value to set/apply.
            operation: Update operation.
            description: Human-readable description.
        """
        rule = UpdateRule(
            agentName=agentName,
            trigger=UpdateTrigger.CONDITION,
            triggerValue=condition,
            updates=[StateUpdate(key=key, value=value, operation=operation)],
            description=description or f"Conditional {operation} {key}",
        )
        self.addRule(rule)

    def addCallback(self, agentName: str, callback: StateUpdateCallback) -> None:
        """Add a callback for dynamic state updates.

        The callback receives (agentName, userInput, response, currentState)
        and returns a dict of updates to apply.

        Args:
            agentName: Agent name.
            callback: Update callback function.
        """
        self._callbacks[agentName] = callback

    def addInteractionCounter(self, agentName: str, key: str = "interactions") -> None:
        """Add an interaction counter for an agent.

        Args:
            agentName: Agent name.
            key: State key for the counter.
        """
        self.addAlwaysUpdate(agentName, key, 1, operation="increment")

    def processInteraction(
        self,
        agentName: str,
        userInput: str,
        response: str,
        currentState: dict[str, Any],
    ) -> dict[str, Any]:
        """Process an interaction and return state updates.

        Args:
            agentName: Agent that responded.
            userInput: User's input.
            response: Agent's response.
            currentState: Current world state.

        Returns:
            Dictionary of updates to apply.
        """
        updates: dict[str, Any] = {}

        # Process rules
        rules = self._rules.get(agentName, [])
        for rule in rules:
            if self._shouldTrigger(rule, userInput, response, currentState):
                for update in rule.updates:
                    value = self._resolveValue(update.value, userInput, response, currentState)
                    updates[update.key] = {
                        "value": value,
                        "operation": update.operation,
                    }
                logger.debug(f"Triggered rule: {rule.description}")

        # Process callback
        if agentName in self._callbacks:
            callback = self._callbacks[agentName]
            try:
                callbackUpdates = callback(agentName, userInput, response, currentState)
                for key, value in callbackUpdates.items():
                    if isinstance(value, dict) and "operation" in value:
                        updates[key] = value
                    else:
                        updates[key] = {"value": value, "operation": "set"}
            except Exception as e:
                logger.warning(f"State update callback error: {e}")

        return updates

    def _shouldTrigger(
        self,
        rule: UpdateRule,
        userInput: str,
        response: str,
        currentState: dict[str, Any],
    ) -> bool:
        """Check if a rule should trigger."""
        if rule.trigger == UpdateTrigger.ALWAYS:
            return True

        if rule.trigger == UpdateTrigger.PATTERN:
            try:
                return bool(re.search(rule.triggerValue, response, re.IGNORECASE))
            except re.error:
                return False

        if rule.trigger == UpdateTrigger.KEYWORD:
            keywords: list[str] = rule.triggerValue
            responseLower = response.lower()
            return any(kw.lower() in responseLower for kw in keywords)

        if rule.trigger == UpdateTrigger.CONDITION:
            try:
                return rule.triggerValue(userInput, response, currentState)
            except Exception:
                return False

        return False

    def _resolveValue(
        self,
        value: Any,
        userInput: str,
        response: str,
        currentState: dict[str, Any],
    ) -> Any:
        """Resolve a value, calling it if it's callable."""
        if callable(value):
            try:
                return value(userInput, response, currentState)
            except Exception as e:
                logger.warning(f"Value resolver error: {e}")
                return None
        return value

    def applyUpdates(
        self,
        updates: dict[str, Any],
        currentState: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply updates to state.

        Args:
            updates: Updates from processInteraction.
            currentState: Current state to modify.

        Returns:
            New state with updates applied.
        """
        newState = currentState.copy()

        for key, updateInfo in updates.items():
            value = updateInfo["value"]
            operation = updateInfo.get("operation", "set")

            if operation == "set":
                newState[key] = value
            elif operation == "increment":
                current = newState.get(key, 0)
                newState[key] = current + value
            elif operation == "append":
                current = newState.get(key, [])
                if isinstance(current, list):
                    newState[key] = current + [value]
                else:
                    newState[key] = [current, value]
            elif operation == "merge":
                current = newState.get(key, {})
                if isinstance(current, dict) and isinstance(value, dict):
                    newState[key] = {**current, **value}
                else:
                    newState[key] = value
            elif operation == "delete":
                newState.pop(key, None)

        return newState

    def hasRules(self, agentName: str) -> bool:
        """Check if an agent has update rules."""
        hasRules = agentName in self._rules and len(self._rules[agentName]) > 0
        hasCallback = agentName in self._callbacks
        return hasRules or hasCallback

    def getRules(self, agentName: str) -> list[UpdateRule]:
        """Get rules for an agent."""
        return self._rules.get(agentName, []).copy()

    def clearRules(self, agentName: str | None = None) -> None:
        """Clear rules for an agent or all agents."""
        if agentName:
            self._rules.pop(agentName, None)
            self._callbacks.pop(agentName, None)
        else:
            self._rules.clear()
            self._callbacks.clear()


def extractNumber(response: str, pattern: str | None = None) -> int | float | None:
    """Helper to extract a number from a response.

    Args:
        response: Agent's response text.
        pattern: Optional regex pattern (should have a capture group).

    Returns:
        Extracted number or None.
    """
    if pattern:
        match = re.search(pattern, response)
        if match:
            try:
                text = match.group(1) if match.groups() else match.group(0)
                return float(text) if "." in text else int(text)
            except (ValueError, IndexError):
                return None
    else:
        # Find first number
        match = re.search(r"-?\d+\.?\d*", response)
        if match:
            text = match.group(0)
            return float(text) if "." in text else int(text)
    return None


def extractBoolean(response: str, trueKeywords: list[str] | None = None) -> bool | None:
    """Helper to extract a boolean from a response.

    Args:
        response: Agent's response text.
        trueKeywords: Keywords indicating True.

    Returns:
        Extracted boolean or None.
    """
    responseLower = response.lower()
    trueKeywords = trueKeywords or ["yes", "true", "agree", "accept", "approve", "confirm"]
    falseKeywords = ["no", "false", "disagree", "reject", "deny", "refuse"]

    for kw in trueKeywords:
        if kw in responseLower:
            return True

    for kw in falseKeywords:
        if kw in responseLower:
            return False

    return None
