"""Tests for cost estimation."""

import pytest

from pm6.agents import AgentConfig
from pm6.cost import CostEstimate, CostEstimator
from pm6.core import Simulation


class TestCostEstimator:
    """Tests for CostEstimator."""

    def test_estimate_interaction(self):
        """Test basic interaction estimation."""
        estimator = CostEstimator()

        estimate = estimator.estimateInteraction()

        assert estimate.estimatedCost > 0
        assert estimate.inputTokens > 0
        assert estimate.outputTokens > 0
        assert estimate.interactions == 1

    def test_estimate_with_input_text(self):
        """Test estimation with actual input text."""
        estimator = CostEstimator()

        short = estimator.estimateInteraction(inputText="Hi")
        long = estimator.estimateInteraction(inputText="This is a much longer input that should estimate more tokens")

        assert long.inputTokens >= short.inputTokens

    def test_estimate_batch(self):
        """Test batch estimation."""
        estimator = CostEstimator()

        single = estimator.estimateInteraction()
        batch = estimator.estimateBatch(10)

        assert batch.interactions == 10
        # With 0% cache hit rate, batch should be ~10x single
        assert batch.estimatedCost > single.estimatedCost * 5

    def test_cache_hit_rate(self):
        """Test cache hit rate affects estimates."""
        estimator = CostEstimator(cacheHitRate=0.0)
        noCacheEstimate = estimator.estimateInteraction()

        estimator.setCacheHitRate(0.5)
        withCacheEstimate = estimator.estimateInteraction()

        assert withCacheEstimate.estimatedCost < noCacheEstimate.estimatedCost

    def test_model_pricing(self):
        """Test different model pricing."""
        estimator = CostEstimator()

        haiku = estimator.estimateInteraction(model="claude-haiku-3-20240307")
        sonnet = estimator.estimateInteraction(model="claude-sonnet-4-20250514")
        opus = estimator.estimateInteraction(model="claude-opus-4-20250514")

        # Haiku should be cheapest, Opus most expensive
        assert haiku.estimatedCost < sonnet.estimatedCost < opus.estimatedCost

    def test_estimate_session(self):
        """Test session estimation."""
        estimator = CostEstimator()

        estimate = estimator.estimateSession(turns=20, agentCount=3)

        assert estimate.interactions > 20  # Multiple agents per turn
        assert estimate.details.get("turns") == 20
        assert estimate.details.get("agentCount") == 3

    def test_set_token_estimates(self):
        """Test custom token estimates per agent."""
        estimator = CostEstimator()

        estimator.setTokenEstimates(
            "verbose_agent",
            inputTokens=1000,
            outputTokens=500,
        )

        default = estimator.estimateInteraction()
        custom = estimator.estimateInteraction(agentName="verbose_agent")

        assert custom.inputTokens > default.inputTokens
        assert custom.outputTokens > default.outputTokens

    def test_will_exceed_limit(self):
        """Test budget limit checking."""
        estimator = CostEstimator()

        estimate = CostEstimate(estimatedCost=0.10)

        # Under limit
        assert not estimator.willExceedLimit(estimate, limit=1.0, currentCost=0.5)

        # Over limit
        assert estimator.willExceedLimit(estimate, limit=1.0, currentCost=0.95)

    def test_remaining_budget(self):
        """Test remaining budget calculation."""
        estimator = CostEstimator()

        budget = estimator.getRemainingBudget(limit=1.0, currentCost=0.7)

        assert budget["remaining"] == pytest.approx(0.3)
        assert budget["percentUsed"] == 70.0
        assert not budget["warning"]  # 70% is below 80% threshold
        assert not budget["critical"]

    def test_cost_estimate_to_dict(self):
        """Test CostEstimate serialization."""
        estimate = CostEstimate(
            estimatedCost=0.01,
            minCost=0.005,
            maxCost=0.02,
            inputTokens=500,
            outputTokens=200,
            model="claude-sonnet-4-20250514",
            interactions=1,
        )

        d = estimate.toDict()

        assert d["estimatedCost"] == 0.01
        assert d["inputTokens"] == 500
        assert "costRange" in d

    def test_format_estimate(self):
        """Test estimate formatting."""
        estimator = CostEstimator()
        estimate = estimator.estimateInteraction()

        formatted = estimator.formatEstimate(estimate)

        assert "Cost Estimate" in formatted
        assert "Model:" in formatted
        assert "tokens" in formatted


class TestSimulationCostEstimation:
    """Tests for cost estimation in Simulation."""

    def test_estimate_interaction_cost(self, tmp_path):
        """Test estimating interaction cost."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        agent = AgentConfig(
            name="test",
            role="Test",
            systemPrompt="You are a test assistant with a moderately long prompt.",
        )
        sim.registerAgent(agent)

        estimate = sim.estimateInteractionCost(agentName="test")

        assert estimate.estimatedCost > 0
        assert estimate.model == agent.model

    def test_estimate_session_cost(self, tmp_path):
        """Test estimating session cost."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        for i in range(3):
            sim.registerAgent(AgentConfig(name=f"agent{i}", role=f"Agent {i}"))

        estimate = sim.estimateSessionCost(turns=10)

        assert estimate.interactions > 10
        assert estimate.estimatedCost > 0

    def test_remaining_budget(self, tmp_path):
        """Test remaining budget with cost limit."""
        sim = Simulation(
            name="test",
            dbPath=tmp_path,
            testMode=True,
            maxCost=1.0,
        )

        budget = sim.getRemainingBudget()

        assert budget is not None
        assert budget["limit"] == 1.0
        assert budget["remaining"] == 1.0

    def test_remaining_budget_no_limit(self, tmp_path):
        """Test remaining budget without cost limit."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        budget = sim.getRemainingBudget()

        assert budget is None

    def test_will_exceed_budget(self, tmp_path):
        """Test budget exceed checking."""
        sim = Simulation(
            name="test",
            dbPath=tmp_path,
            testMode=True,
            maxCost=0.001,  # Very low limit
        )

        # With such a low limit, any operation should exceed
        assert sim.willExceedBudget(interactions=10)

    def test_will_exceed_no_limit(self, tmp_path):
        """Test budget exceed with no limit set."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        # No limit means never exceed
        assert not sim.willExceedBudget(interactions=1000)

    def test_cost_estimator_property(self, tmp_path):
        """Test accessing cost estimator directly."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        estimator = sim.costEstimator
        assert estimator is not None
        assert isinstance(estimator, CostEstimator)
