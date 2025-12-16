"""Tests for agent relevance detection."""

import pytest

from pm6.agents import (
    AgentConfig,
    AgentRelevanceDetector,
    RelevanceRule,
    RelevanceStrategy,
)
from pm6.core import Simulation


class TestAgentRelevanceDetector:
    """Tests for AgentRelevanceDetector."""

    def test_keyword_matching(self):
        """Test keyword-based relevance."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("finance_agent", ["budget", "money", "tax"])

        # Matching input
        score = detector.scoreAgent(
            "finance_agent", "What's the budget plan?", {}, None, None
        )
        assert score.isRelevant
        assert score.score > 0

        # Non-matching input
        score = detector.scoreAgent(
            "finance_agent", "What's the weather?", {}, None, None
        )
        assert not score.isRelevant

    def test_multiple_keywords(self):
        """Test multiple keyword matches increase score."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent", ["budget", "money", "tax"])

        score1 = detector.scoreAgent("agent", "budget plan", {}, None, None)
        score2 = detector.scoreAgent("agent", "budget and money", {}, None, None)
        score3 = detector.scoreAgent("agent", "budget, money, and tax", {}, None, None)

        assert score1.score < score2.score < score3.score

    def test_case_insensitive_keywords(self):
        """Test case-insensitive keyword matching."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent", ["Budget", "MONEY"], caseSensitive=False)

        score = detector.scoreAgent("agent", "what about the budget?", {}, None, None)
        assert score.isRelevant

    def test_pattern_matching(self):
        """Test regex pattern matching."""
        detector = AgentRelevanceDetector()
        detector.addPattern("email_agent", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

        score = detector.scoreAgent(
            "email_agent", "Contact me at test@example.com", {}, None, None
        )
        assert score.isRelevant

        score = detector.scoreAgent(
            "email_agent", "No email here", {}, None, None
        )
        assert not score.isRelevant

    def test_state_condition(self):
        """Test state-based relevance."""
        detector = AgentRelevanceDetector()
        detector.addStateCondition(
            "crisis_agent",
            lambda state: state.get("crisis_level", 0) > 5,
        )

        # State meets condition
        score = detector.scoreAgent(
            "crisis_agent", "Any input", {"crisis_level": 8}, None, None
        )
        assert score.isRelevant

        # State doesn't meet condition
        score = detector.scoreAgent(
            "crisis_agent", "Any input", {"crisis_level": 2}, None, None
        )
        assert not score.isRelevant

    def test_situation_type_matching(self):
        """Test situation type matching."""
        detector = AgentRelevanceDetector()
        detector.addSituationTypes("diplomacy_agent", ["negotiation", "treaty"])

        score = detector.scoreAgent(
            "diplomacy_agent", "Any input", {}, "negotiation", None
        )
        assert score.isRelevant

        score = detector.scoreAgent(
            "diplomacy_agent", "Any input", {}, "combat", None
        )
        assert not score.isRelevant

    def test_always_relevant(self):
        """Test always-relevant agents."""
        detector = AgentRelevanceDetector()
        detector.setAlwaysRelevant("narrator")

        score = detector.scoreAgent("narrator", "Any input", {}, None, None)
        assert score.isRelevant
        assert score.score == 1.0

    def test_weighted_rules(self):
        """Test weighted rules."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent", ["budget"], weight=0.3)
        detector.addStateCondition(
            "agent", lambda s: s.get("finance_mode", False), weight=0.7
        )

        # Only keywords match (30% weight)
        score = detector.scoreAgent("agent", "budget plan", {"finance_mode": False}, None, None)
        assert abs(score.score - 0.3) < 0.01

        # Both match (100%)
        score = detector.scoreAgent("agent", "budget plan", {"finance_mode": True}, None, None)
        assert abs(score.score - 1.0) < 0.01

    def test_get_relevant_agents(self):
        """Test getting multiple relevant agents."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("finance", ["budget", "money"])
        detector.addKeywords("politics", ["election", "vote"])
        detector.setAlwaysRelevant("narrator")

        agents = [
            AgentConfig(name="finance", role="Finance"),
            AgentConfig(name="politics", role="Politics"),
            AgentConfig(name="narrator", role="Narrator"),
        ]

        relevant = detector.getRelevantAgents(agents, "budget plan", {})
        names = [a.name for a, _ in relevant]

        assert "finance" in names
        assert "narrator" in names
        assert "politics" not in names

    def test_threshold_filtering(self):
        """Test threshold-based filtering."""
        detector = AgentRelevanceDetector(threshold=0.5)
        detector.addKeywords("agent", ["one", "two", "three", "four"])

        # Only 1 of 4 keywords = 0.25 (below threshold)
        score = detector.scoreAgent("agent", "one match", {}, None, None)
        assert not score.isRelevant

        # 3 of 4 keywords = 0.75 (above threshold)
        score = detector.scoreAgent("agent", "one two three", {}, None, None)
        assert score.isRelevant

    def test_top_k_agents(self):
        """Test limiting to top K agents."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent1", ["test"])
        detector.addKeywords("agent2", ["test"])
        detector.addKeywords("agent3", ["test"])

        agents = [
            AgentConfig(name="agent1", role="A1"),
            AgentConfig(name="agent2", role="A2"),
            AgentConfig(name="agent3", role="A3"),
        ]

        relevant = detector.getRelevantAgents(agents, "test input", {}, topK=2)
        assert len(relevant) == 2

    def test_matched_rules_reporting(self):
        """Test that matched rules are reported."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent", ["budget"])
        detector.addStateCondition(
            "agent", lambda s: True, description="Always true condition"
        )

        score = detector.scoreAgent("agent", "budget plan", {}, None, None)

        assert len(score.matchedRules) == 2
        assert any("budget" in r for r in score.matchedRules)
        assert any("Always true" in r for r in score.matchedRules)

    def test_clear_rules(self):
        """Test clearing rules."""
        detector = AgentRelevanceDetector()
        detector.addKeywords("agent", ["test"])

        assert detector.hasRules("agent")

        detector.clearRules("agent")

        assert not detector.hasRules("agent")


class TestSimulationRelevance:
    """Tests for relevance detection in Simulation."""

    def test_add_agent_keywords(self, tmp_path):
        """Test adding keywords via Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(name="finance", role="Finance Minister")
        sim.registerAgent(agent)

        sim.addAgentKeywords("finance", ["budget", "money", "economy"])

        relevant = sim.getRelevantAgents("What's the budget?")
        names = [name for name, _ in relevant]
        assert "finance" in names

    def test_add_relevance_condition(self, tmp_path):
        """Test adding state conditions via Simulation."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(name="crisis", role="Crisis Manager")
        sim.registerAgent(agent)

        sim.addAgentRelevanceCondition(
            "crisis",
            lambda state: state.get("crisis", False),
            description="Active crisis",
        )

        # No crisis
        sim.setWorldState({"crisis": False})
        relevant = sim.getRelevantAgents("Any input")
        assert len(relevant) == 0

        # Crisis active
        sim.setWorldState({"crisis": True})
        relevant = sim.getRelevantAgents("Any input")
        names = [name for name, _ in relevant]
        assert "crisis" in names

    def test_always_relevant_agent(self, tmp_path):
        """Test marking agent as always relevant."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(name="narrator", role="Narrator")
        sim.registerAgent(agent)

        sim.setAgentAlwaysRelevant("narrator")

        relevant = sim.getRelevantAgents("Any random input")
        names = [name for name, _ in relevant]
        assert "narrator" in names

    def test_score_agent_relevance(self, tmp_path):
        """Test scoring individual agent relevance."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(name="test", role="Test")
        sim.registerAgent(agent)

        sim.addAgentKeywords("test", ["keyword"])

        score = sim.scoreAgentRelevance("test", "This has the keyword")
        assert score.isRelevant
        assert score.score > 0

    def test_relevance_detector_property(self, tmp_path):
        """Test accessing relevance detector directly."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        detector = sim.relevanceDetector
        assert detector is not None
        assert isinstance(detector, AgentRelevanceDetector)
