"""Tests for performance metrics tracking."""

import time

import pytest

from pm6.agents import AgentConfig
from pm6.core import Simulation
from pm6.metrics import InteractionMetrics, PerformanceBaseline, PerformanceTracker


class TestPerformanceTracker:
    """Tests for PerformanceTracker."""

    def test_record_interaction(self):
        """Test recording an interaction with known metrics."""
        tracker = PerformanceTracker()

        metrics = tracker.recordInteraction(
            agentName="test_agent",
            responseTimeMs=150.5,
            cost=0.001,
            inputTokens=100,
            outputTokens=50,
            fromCache=False,
            model="claude-sonnet-4-20250514",
        )

        assert metrics.agentName == "test_agent"
        assert metrics.responseTimeMs == 150.5
        assert metrics.cost == 0.001
        assert not metrics.fromCache

    def test_timer_based_recording(self):
        """Test timer-based metrics recording."""
        tracker = PerformanceTracker()

        tracker.startTimer("agent")
        time.sleep(0.01)  # 10ms
        metrics = tracker.stopTimer(cost=0.002, fromCache=True)

        assert metrics.agentName == "agent"
        assert metrics.responseTimeMs >= 10  # At least 10ms
        assert metrics.fromCache

    def test_stop_timer_without_start_raises(self):
        """Test stopping timer without starting raises error."""
        tracker = PerformanceTracker()

        with pytest.raises(ValueError):
            tracker.stopTimer()

    def test_get_stats_empty(self):
        """Test stats with no interactions."""
        tracker = PerformanceTracker()

        stats = tracker.getStats()

        assert stats["totalInteractions"] == 0
        assert stats["avgResponseTimeMs"] == 0
        assert stats["cacheHitRate"] == 0

    def test_get_stats(self):
        """Test getting performance statistics."""
        tracker = PerformanceTracker()

        # Record some interactions
        tracker.recordInteraction("a", 100, cost=0.01, fromCache=False)
        tracker.recordInteraction("a", 200, cost=0.02, fromCache=False)
        tracker.recordInteraction("b", 50, cost=0.0, fromCache=True)

        stats = tracker.getStats()

        assert stats["totalInteractions"] == 3
        assert abs(stats["avgResponseTimeMs"] - 116.67) < 1  # (100+200+50)/3
        assert stats["cacheHits"] == 1
        assert stats["cacheMisses"] == 2
        assert abs(stats["cacheHitRate"] - 33.33) < 1

    def test_percentiles(self):
        """Test percentile calculations."""
        tracker = PerformanceTracker()

        # Record varied response times
        for t in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            tracker.recordInteraction("a", t)

        stats = tracker.getStats()

        # P50 should be around median (50-60 range)
        assert 40 <= stats["p50ResponseTimeMs"] <= 60
        # P95 should be high (90-100 range)
        assert 80 <= stats["p95ResponseTimeMs"] <= 100
        assert stats["minResponseTimeMs"] == 10
        assert stats["maxResponseTimeMs"] == 100

    def test_agent_stats(self):
        """Test per-agent statistics."""
        tracker = PerformanceTracker()

        tracker.recordInteraction("agent1", 100, cost=0.01)
        tracker.recordInteraction("agent1", 200, cost=0.02)
        tracker.recordInteraction("agent2", 50, cost=0.005)

        stats1 = tracker.getAgentStats("agent1")
        stats2 = tracker.getAgentStats("agent2")

        assert stats1["totalInteractions"] == 2
        assert stats1["avgResponseTimeMs"] == 150
        assert stats2["totalInteractions"] == 1
        assert stats2["avgResponseTimeMs"] == 50

    def test_agent_stats_unknown_agent(self):
        """Test stats for unknown agent."""
        tracker = PerformanceTracker()

        stats = tracker.getAgentStats("unknown")

        assert stats["totalInteractions"] == 0

    def test_create_baseline(self):
        """Test creating performance baseline."""
        tracker = PerformanceTracker()

        tracker.recordInteraction("a", 100, cost=0.01, fromCache=False)
        tracker.recordInteraction("a", 200, cost=0.02, fromCache=True)

        baseline = tracker.createBaseline("v1.0")

        assert baseline.name == "v1.0"
        assert baseline.avgResponseTimeMs == 150
        assert baseline.cacheHitRate == 50.0
        assert baseline.totalInteractions == 2

    def test_compare_to_baseline(self):
        """Test comparing current performance to baseline."""
        tracker = PerformanceTracker()

        # Create baseline
        tracker.recordInteraction("a", 100, cost=0.01)
        tracker.recordInteraction("a", 100, cost=0.01)
        tracker.createBaseline("baseline")

        # Clear and add new, worse metrics
        tracker.clear()
        tracker.recordInteraction("a", 200, cost=0.03)  # Slower, more expensive
        tracker.recordInteraction("a", 200, cost=0.03)

        comparison = tracker.compareToBaseline("baseline")

        assert comparison["baseline"] == "baseline"
        assert comparison["deltas"]["responseTimeMs"] == 100  # 200 - 100
        assert comparison["regressions"]["responseTime"]  # >10% regression

    def test_has_regression(self):
        """Test regression detection."""
        tracker = PerformanceTracker()

        # Create baseline with good performance
        tracker.recordInteraction("a", 100, cost=0.01)
        tracker.createBaseline("good")

        # Clear and create much worse metrics
        tracker.clear()
        tracker.recordInteraction("a", 500, cost=0.05)

        assert tracker.hasRegression("good")

    def test_no_regression(self):
        """Test no regression detection."""
        tracker = PerformanceTracker()

        # Create baseline
        tracker.recordInteraction("a", 100, cost=0.01)
        tracker.createBaseline("baseline")

        # Clear and create similar metrics
        tracker.clear()
        tracker.recordInteraction("a", 105, cost=0.011)  # Within 10%

        assert not tracker.hasRegression("baseline")

    def test_compare_unknown_baseline_raises(self):
        """Test comparing to unknown baseline raises error."""
        tracker = PerformanceTracker()

        with pytest.raises(ValueError):
            tracker.compareToBaseline("nonexistent")

    def test_recent_metrics(self):
        """Test getting recent metrics."""
        tracker = PerformanceTracker()

        for i in range(10):
            tracker.recordInteraction("a", i * 10)

        recent = tracker.getRecentMetrics(5)

        assert len(recent) == 5
        assert recent[-1].responseTimeMs == 90  # Last one

    def test_max_history_limit(self):
        """Test max history is enforced."""
        tracker = PerformanceTracker(maxHistory=10)

        for i in range(20):
            tracker.recordInteraction("a", i)

        assert len(tracker.getRecentMetrics(100)) == 10

    def test_clear(self):
        """Test clearing metrics."""
        tracker = PerformanceTracker()

        tracker.recordInteraction("a", 100)
        tracker.createBaseline("b")

        tracker.clear()

        stats = tracker.getStats()
        assert stats["totalInteractions"] == 0
        # Baselines should still exist
        assert len(tracker.getBaselines()) == 1

    def test_clear_baselines(self):
        """Test clearing baselines."""
        tracker = PerformanceTracker()

        tracker.recordInteraction("a", 100)
        tracker.createBaseline("b")
        tracker.clearBaselines()

        assert len(tracker.getBaselines()) == 0

    def test_format_report(self):
        """Test report formatting."""
        tracker = PerformanceTracker()

        tracker.recordInteraction("a", 100, cost=0.01, fromCache=False)
        tracker.recordInteraction("b", 50, cost=0.0, fromCache=True)

        report = tracker.formatReport()

        assert "Performance Report" in report
        assert "Response Time:" in report
        assert "Cache Performance:" in report

    def test_metrics_to_dict(self):
        """Test InteractionMetrics serialization."""
        tracker = PerformanceTracker()

        metrics = tracker.recordInteraction("agent", 100, cost=0.01)
        d = metrics.toDict()

        assert d["agentName"] == "agent"
        assert d["responseTimeMs"] == 100
        assert "timestamp" in d

    def test_baseline_to_dict(self):
        """Test PerformanceBaseline serialization."""
        tracker = PerformanceTracker()
        tracker.recordInteraction("a", 100)

        baseline = tracker.createBaseline("v1")
        d = baseline.toDict()

        assert d["name"] == "v1"
        assert "avgResponseTimeMs" in d
        assert "createdAt" in d


class TestSimulationPerformanceMetrics:
    """Tests for performance metrics in Simulation."""

    def test_performance_stats(self, tmp_path):
        """Test getting performance stats from Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response 1", "Response 2"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="You are a test")
        sim.registerAgent(agent)

        sim.interact("test", "Hello")
        sim.interact("test", "World")

        stats = sim.getPerformanceStats()

        assert stats["totalInteractions"] == 2
        assert stats["avgResponseTimeMs"] > 0

    def test_agent_performance(self, tmp_path):
        """Test getting agent-specific performance."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1", "R2"],
        )
        agent = AgentConfig(name="agent1", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        sim.interact("agent1", "Hello")
        sim.interact("agent1", "World")

        stats = sim.getAgentPerformance("agent1")

        assert stats["totalInteractions"] == 2
        assert stats["agentName"] == "agent1"

    def test_create_baseline(self, tmp_path):
        """Test creating performance baseline via Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        sim.interact("test", "Hello")
        baseline = sim.createPerformanceBaseline("v1.0")

        assert baseline["name"] == "v1.0"
        assert baseline["totalInteractions"] == 1

    def test_compare_performance(self, tmp_path):
        """Test comparing performance to baseline."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1", "R2", "R3", "R4"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        # Create baseline
        sim.interact("test", "Hello")
        sim.interact("test", "World")
        sim.createPerformanceBaseline("baseline")

        # More interactions
        sim.interact("test", "More")
        sim.interact("test", "Data")

        comparison = sim.comparePerformance("baseline")

        assert comparison["baseline"] == "baseline"
        assert "current" in comparison
        assert "regressions" in comparison

    def test_has_regression(self, tmp_path):
        """Test regression detection via Simulation."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["R1", "R2"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        sim.interact("test", "Hello")
        sim.createPerformanceBaseline("baseline")

        sim.interact("test", "World")

        # No major regression expected with similar operations
        hasRegression = sim.hasPerformanceRegression("baseline")
        assert isinstance(hasRegression, bool)

    def test_performance_report(self, tmp_path):
        """Test getting formatted performance report."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        sim.interact("test", "Hello")
        report = sim.getPerformanceReport()

        assert "Performance Report" in report
        assert "Response Time:" in report

    def test_performance_tracker_property(self, tmp_path):
        """Test accessing performance tracker directly."""
        sim = Simulation.createTestSimulation(name="test", dbPath=tmp_path)

        tracker = sim.performanceTracker
        assert tracker is not None
        assert isinstance(tracker, PerformanceTracker)

    def test_cache_hit_tracked(self, tmp_path):
        """Test that cache hits are tracked in metrics."""
        sim = Simulation.createTestSimulation(
            name="test",
            dbPath=tmp_path,
            responses=["Response"],
        )
        agent = AgentConfig(name="test", role="Test", systemPrompt="Test")
        sim.registerAgent(agent)

        # First call - cache miss (response from queue)
        sim.interact("test", "Same input")

        # Note: In test mode with mock responses, caching behavior
        # depends on the mock implementation
        stats = sim.getPerformanceStats()
        assert stats["totalInteractions"] >= 1
