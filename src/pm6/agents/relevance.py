"""Agent relevance detection for cost optimization.

Determines which agents are relevant for a given interaction,
enabling the system to only activate necessary agents.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pm6.agents.agentConfig import AgentConfig

logger = logging.getLogger("pm6.agents")


class RelevanceStrategy(str, Enum):
    """Strategies for determining agent relevance."""

    KEYWORD = "keyword"  # Match keywords in input
    PATTERN = "pattern"  # Match regex patterns
    STATE = "state"  # Match world state conditions
    SITUATION = "situation"  # Match situation types
    CUSTOM = "custom"  # Custom callback function
    ALWAYS = "always"  # Agent is always relevant


@dataclass
class RelevanceRule:
    """A rule for determining agent relevance.

    Attributes:
        strategy: The matching strategy.
        value: Strategy-specific value (keywords, pattern, condition).
        weight: Importance weight for scoring (0.0 to 1.0).
        description: Human-readable description.
    """

    strategy: RelevanceStrategy
    value: Any
    weight: float = 1.0
    description: str = ""


@dataclass
class RelevanceScore:
    """Score indicating how relevant an agent is.

    Attributes:
        agentName: Name of the agent.
        score: Relevance score (0.0 to 1.0).
        matchedRules: Rules that matched.
        isRelevant: Whether agent meets relevance threshold.
    """

    agentName: str
    score: float
    matchedRules: list[str] = field(default_factory=list)
    isRelevant: bool = False


# Type for custom relevance functions
RelevanceCallback = Callable[[str, dict[str, Any], AgentConfig], float]


class AgentRelevanceDetector:
    """Detects which agents are relevant for an interaction.

    Uses multiple strategies to score agent relevance:
    - Keyword matching in user input
    - Regex pattern matching
    - World state conditions
    - Situation type matching
    - Custom callback functions

    Args:
        threshold: Minimum score for an agent to be considered relevant.
    """

    def __init__(self, threshold: float = 0.1):
        self._threshold = threshold
        self._agentRules: dict[str, list[RelevanceRule]] = {}
        self._customCallbacks: dict[str, RelevanceCallback] = {}
        self._globalRules: list[RelevanceRule] = []

    def setThreshold(self, threshold: float) -> None:
        """Set the relevance threshold.

        Args:
            threshold: Minimum score (0.0 to 1.0) to be relevant.
        """
        self._threshold = max(0.0, min(1.0, threshold))

    def addRule(self, agentName: str, rule: RelevanceRule) -> None:
        """Add a relevance rule for an agent.

        Args:
            agentName: Agent to add rule for.
            rule: The relevance rule.
        """
        if agentName not in self._agentRules:
            self._agentRules[agentName] = []
        self._agentRules[agentName].append(rule)

    def addKeywords(
        self,
        agentName: str,
        keywords: list[str],
        weight: float = 1.0,
        caseSensitive: bool = False,
    ) -> None:
        """Add keyword matching for an agent.

        Args:
            agentName: Agent name.
            keywords: Keywords to match in input.
            weight: Importance weight.
            caseSensitive: Whether matching is case-sensitive.
        """
        rule = RelevanceRule(
            strategy=RelevanceStrategy.KEYWORD,
            value={"keywords": keywords, "caseSensitive": caseSensitive},
            weight=weight,
            description=f"Keywords: {', '.join(keywords)}",
        )
        self.addRule(agentName, rule)

    def addPattern(
        self,
        agentName: str,
        pattern: str,
        weight: float = 1.0,
    ) -> None:
        """Add regex pattern matching for an agent.

        Args:
            agentName: Agent name.
            pattern: Regex pattern to match.
            weight: Importance weight.
        """
        rule = RelevanceRule(
            strategy=RelevanceStrategy.PATTERN,
            value=pattern,
            weight=weight,
            description=f"Pattern: {pattern}",
        )
        self.addRule(agentName, rule)

    def addStateCondition(
        self,
        agentName: str,
        condition: Callable[[dict[str, Any]], bool],
        weight: float = 1.0,
        description: str = "",
    ) -> None:
        """Add a state-based condition for an agent.

        Args:
            agentName: Agent name.
            condition: Function that checks world state.
            weight: Importance weight.
            description: Human-readable description.
        """
        rule = RelevanceRule(
            strategy=RelevanceStrategy.STATE,
            value=condition,
            weight=weight,
            description=description or "State condition",
        )
        self.addRule(agentName, rule)

    def addSituationTypes(
        self,
        agentName: str,
        situationTypes: list[str],
        weight: float = 1.0,
    ) -> None:
        """Add situation type matching for an agent.

        Args:
            agentName: Agent name.
            situationTypes: Situation types this agent handles.
            weight: Importance weight.
        """
        rule = RelevanceRule(
            strategy=RelevanceStrategy.SITUATION,
            value=situationTypes,
            weight=weight,
            description=f"Situations: {', '.join(situationTypes)}",
        )
        self.addRule(agentName, rule)

    def addCustomCallback(
        self,
        agentName: str,
        callback: RelevanceCallback,
        weight: float = 1.0,
    ) -> None:
        """Add a custom relevance callback for an agent.

        Args:
            agentName: Agent name.
            callback: Function(input, state, agent) -> score.
            weight: Importance weight.
        """
        self._customCallbacks[agentName] = callback
        rule = RelevanceRule(
            strategy=RelevanceStrategy.CUSTOM,
            value=callback,
            weight=weight,
            description="Custom callback",
        )
        self.addRule(agentName, rule)

    def setAlwaysRelevant(self, agentName: str) -> None:
        """Mark an agent as always relevant.

        Args:
            agentName: Agent to mark.
        """
        rule = RelevanceRule(
            strategy=RelevanceStrategy.ALWAYS,
            value=True,
            weight=1.0,
            description="Always relevant",
        )
        self.addRule(agentName, rule)

    def scoreAgent(
        self,
        agentName: str,
        userInput: str,
        worldState: dict[str, Any],
        situationType: str | None = None,
        agent: AgentConfig | None = None,
    ) -> RelevanceScore:
        """Calculate relevance score for an agent.

        Args:
            agentName: Agent to score.
            userInput: User's input text.
            worldState: Current world state.
            situationType: Current situation type.
            agent: Agent config (for custom callbacks).

        Returns:
            RelevanceScore with score and matched rules.
        """
        rules = self._agentRules.get(agentName, [])
        if not rules:
            return RelevanceScore(agentName=agentName, score=0.0, isRelevant=False)

        totalWeight = sum(r.weight for r in rules)
        score = 0.0
        matchedRules: list[str] = []

        for rule in rules:
            ruleScore = self._evaluateRule(
                rule, userInput, worldState, situationType, agent
            )
            if ruleScore > 0:
                matchedRules.append(rule.description)
                score += ruleScore * rule.weight

        if totalWeight > 0:
            score = score / totalWeight

        return RelevanceScore(
            agentName=agentName,
            score=score,
            matchedRules=matchedRules,
            isRelevant=score >= self._threshold,
        )

    def _evaluateRule(
        self,
        rule: RelevanceRule,
        userInput: str,
        worldState: dict[str, Any],
        situationType: str | None,
        agent: AgentConfig | None,
    ) -> float:
        """Evaluate a single rule.

        Returns score between 0.0 and 1.0.
        """
        if rule.strategy == RelevanceStrategy.ALWAYS:
            return 1.0

        if rule.strategy == RelevanceStrategy.KEYWORD:
            return self._evaluateKeywords(userInput, rule.value)

        if rule.strategy == RelevanceStrategy.PATTERN:
            return self._evaluatePattern(userInput, rule.value)

        if rule.strategy == RelevanceStrategy.STATE:
            return self._evaluateState(worldState, rule.value)

        if rule.strategy == RelevanceStrategy.SITUATION:
            return self._evaluateSituation(situationType, rule.value)

        if rule.strategy == RelevanceStrategy.CUSTOM:
            if agent:
                return rule.value(userInput, worldState, agent)
            return 0.0

        return 0.0

    def _evaluateKeywords(self, userInput: str, config: dict[str, Any]) -> float:
        """Evaluate keyword matching."""
        keywords: list[str] = config.get("keywords", [])
        caseSensitive: bool = config.get("caseSensitive", False)

        if not keywords:
            return 0.0

        if not caseSensitive:
            userInput = userInput.lower()
            keywords = [k.lower() for k in keywords]

        matches = sum(1 for kw in keywords if kw in userInput)
        return matches / len(keywords)

    def _evaluatePattern(self, userInput: str, pattern: str) -> float:
        """Evaluate regex pattern matching."""
        try:
            if re.search(pattern, userInput, re.IGNORECASE):
                return 1.0
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")
        return 0.0

    def _evaluateState(
        self,
        worldState: dict[str, Any],
        condition: Callable[[dict[str, Any]], bool],
    ) -> float:
        """Evaluate state condition."""
        try:
            return 1.0 if condition(worldState) else 0.0
        except Exception as e:
            logger.warning(f"State condition error: {e}")
            return 0.0

    def _evaluateSituation(
        self, situationType: str | None, allowedTypes: list[str]
    ) -> float:
        """Evaluate situation type matching."""
        if situationType and situationType in allowedTypes:
            return 1.0
        return 0.0

    def getRelevantAgents(
        self,
        agents: list[AgentConfig],
        userInput: str,
        worldState: dict[str, Any],
        situationType: str | None = None,
        topK: int | None = None,
    ) -> list[tuple[AgentConfig, RelevanceScore]]:
        """Get relevant agents sorted by relevance score.

        Args:
            agents: List of all agents.
            userInput: User's input text.
            worldState: Current world state.
            situationType: Current situation type.
            topK: Return only top K agents (None for all relevant).

        Returns:
            List of (agent, score) tuples, sorted by score descending.
        """
        scored: list[tuple[AgentConfig, RelevanceScore]] = []

        for agent in agents:
            score = self.scoreAgent(
                agent.name, userInput, worldState, situationType, agent
            )
            if score.isRelevant:
                scored.append((agent, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1].score, reverse=True)

        if topK is not None:
            scored = scored[:topK]

        return scored

    def getAgentNames(
        self,
        agents: list[AgentConfig],
        userInput: str,
        worldState: dict[str, Any],
        situationType: str | None = None,
    ) -> list[str]:
        """Get names of relevant agents.

        Args:
            agents: List of all agents.
            userInput: User's input text.
            worldState: Current world state.
            situationType: Current situation type.

        Returns:
            List of relevant agent names.
        """
        relevant = self.getRelevantAgents(agents, userInput, worldState, situationType)
        return [agent.name for agent, _ in relevant]

    def hasRules(self, agentName: str) -> bool:
        """Check if an agent has relevance rules defined.

        Args:
            agentName: Agent name.

        Returns:
            True if agent has rules.
        """
        return agentName in self._agentRules and len(self._agentRules[agentName]) > 0

    def clearRules(self, agentName: str | None = None) -> None:
        """Clear relevance rules.

        Args:
            agentName: Agent to clear (None for all).
        """
        if agentName:
            self._agentRules.pop(agentName, None)
            self._customCallbacks.pop(agentName, None)
        else:
            self._agentRules.clear()
            self._customCallbacks.clear()

    def getRules(self, agentName: str) -> list[RelevanceRule]:
        """Get rules for an agent.

        Args:
            agentName: Agent name.

        Returns:
            List of relevance rules.
        """
        return self._agentRules.get(agentName, []).copy()
