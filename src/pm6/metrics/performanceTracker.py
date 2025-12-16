"""Performance tracking for response times and metrics.

Supports NFR1-5:
- NFR1: Response times tracked and reported for every interaction
- NFR2: Cost per interaction logged and visible
- NFR3: DB-hit rate (cache vs LLM) measured
- NFR4: Performance baselines tracked over time
- NFR5: Regression detection via metrics comparison
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean, stdev
from typing import Any

logger = logging.getLogger("pm6.metrics")


@dataclass
class InteractionMetrics:
    """Metrics for a single interaction.

    Attributes:
        timestamp: When the interaction occurred.
        agentName: Agent that handled the interaction.
        responseTimeMs: Response time in milliseconds.
        cost: Cost of the interaction in USD.
        inputTokens: Input tokens used.
        outputTokens: Output tokens generated.
        fromCache: Whether response was from cache.
        model: Model used for the response.
    """

    timestamp: datetime
    agentName: str
    responseTimeMs: float
    cost: float = 0.0
    inputTokens: int = 0
    outputTokens: int = 0
    fromCache: bool = False
    model: str = ""

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "agentName": self.agentName,
            "responseTimeMs": self.responseTimeMs,
            "cost": self.cost,
            "inputTokens": self.inputTokens,
            "outputTokens": self.outputTokens,
            "fromCache": self.fromCache,
            "model": self.model,
        }


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison.

    Attributes:
        name: Baseline name (e.g., "v1.0", "2024-01").
        avgResponseTimeMs: Average response time.
        p95ResponseTimeMs: 95th percentile response time.
        avgCostPerInteraction: Average cost per interaction.
        cacheHitRate: Cache hit percentage.
        totalInteractions: Number of interactions in baseline.
        createdAt: When baseline was created.
    """

    name: str
    avgResponseTimeMs: float
    p95ResponseTimeMs: float
    avgCostPerInteraction: float
    cacheHitRate: float
    totalInteractions: int
    createdAt: datetime = field(default_factory=datetime.now)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "avgResponseTimeMs": self.avgResponseTimeMs,
            "p95ResponseTimeMs": self.p95ResponseTimeMs,
            "avgCostPerInteraction": self.avgCostPerInteraction,
            "cacheHitRate": self.cacheHitRate,
            "totalInteractions": self.totalInteractions,
            "createdAt": self.createdAt.isoformat(),
        }


class PerformanceTracker:
    """Tracks performance metrics for interactions.

    Provides:
    - Real-time response time tracking
    - Cost per interaction logging
    - Cache hit rate measurement
    - Performance baseline comparison
    - Regression detection

    Args:
        maxHistory: Maximum interactions to keep in memory.
    """

    def __init__(self, maxHistory: int = 10000):
        self._maxHistory = maxHistory
        self._interactions: list[InteractionMetrics] = []
        self._baselines: dict[str, PerformanceBaseline] = {}
        self._activeTimer: float | None = None
        self._timerAgentName: str = ""

    def startTimer(self, agentName: str) -> None:
        """Start timing an interaction.

        Args:
            agentName: Agent handling the interaction.
        """
        self._activeTimer = time.perf_counter()
        self._timerAgentName = agentName

    def stopTimer(
        self,
        cost: float = 0.0,
        inputTokens: int = 0,
        outputTokens: int = 0,
        fromCache: bool = False,
        model: str = "",
    ) -> InteractionMetrics:
        """Stop timer and record interaction metrics.

        Args:
            cost: Cost of the interaction.
            inputTokens: Input tokens used.
            outputTokens: Output tokens generated.
            fromCache: Whether response was from cache.
            model: Model used.

        Returns:
            Recorded InteractionMetrics.
        """
        if self._activeTimer is None:
            raise ValueError("No active timer to stop")

        elapsed = time.perf_counter() - self._activeTimer
        responseTimeMs = elapsed * 1000

        metrics = InteractionMetrics(
            timestamp=datetime.now(),
            agentName=self._timerAgentName,
            responseTimeMs=responseTimeMs,
            cost=cost,
            inputTokens=inputTokens,
            outputTokens=outputTokens,
            fromCache=fromCache,
            model=model,
        )

        self._recordMetrics(metrics)
        self._activeTimer = None
        self._timerAgentName = ""

        return metrics

    def recordInteraction(
        self,
        agentName: str,
        responseTimeMs: float,
        cost: float = 0.0,
        inputTokens: int = 0,
        outputTokens: int = 0,
        fromCache: bool = False,
        model: str = "",
    ) -> InteractionMetrics:
        """Record an interaction with known metrics.

        Args:
            agentName: Agent that handled the interaction.
            responseTimeMs: Response time in milliseconds.
            cost: Cost of the interaction.
            inputTokens: Input tokens used.
            outputTokens: Output tokens generated.
            fromCache: Whether response was from cache.
            model: Model used.

        Returns:
            Recorded InteractionMetrics.
        """
        metrics = InteractionMetrics(
            timestamp=datetime.now(),
            agentName=agentName,
            responseTimeMs=responseTimeMs,
            cost=cost,
            inputTokens=inputTokens,
            outputTokens=outputTokens,
            fromCache=fromCache,
            model=model,
        )

        self._recordMetrics(metrics)
        return metrics

    def _recordMetrics(self, metrics: InteractionMetrics) -> None:
        """Internal method to record metrics."""
        self._interactions.append(metrics)

        # Trim history if needed
        if len(self._interactions) > self._maxHistory:
            self._interactions = self._interactions[-self._maxHistory:]

        logger.debug(
            f"Recorded: {metrics.agentName} - {metrics.responseTimeMs:.2f}ms, "
            f"cost=${metrics.cost:.6f}, cache={metrics.fromCache}"
        )

    def getStats(self) -> dict[str, Any]:
        """Get current performance statistics.

        Returns:
            Dictionary with performance metrics.
        """
        if not self._interactions:
            return {
                "totalInteractions": 0,
                "avgResponseTimeMs": 0,
                "p50ResponseTimeMs": 0,
                "p95ResponseTimeMs": 0,
                "p99ResponseTimeMs": 0,
                "minResponseTimeMs": 0,
                "maxResponseTimeMs": 0,
                "totalCost": 0,
                "avgCostPerInteraction": 0,
                "cacheHitRate": 0,
                "cacheHits": 0,
                "cacheMisses": 0,
            }

        times = [m.responseTimeMs for m in self._interactions]
        sortedTimes = sorted(times)
        costs = [m.cost for m in self._interactions]
        cacheHits = sum(1 for m in self._interactions if m.fromCache)
        total = len(self._interactions)

        return {
            "totalInteractions": total,
            "avgResponseTimeMs": mean(times),
            "p50ResponseTimeMs": self._percentile(sortedTimes, 50),
            "p95ResponseTimeMs": self._percentile(sortedTimes, 95),
            "p99ResponseTimeMs": self._percentile(sortedTimes, 99),
            "minResponseTimeMs": min(times),
            "maxResponseTimeMs": max(times),
            "stdDevResponseTimeMs": stdev(times) if len(times) > 1 else 0,
            "totalCost": sum(costs),
            "avgCostPerInteraction": mean(costs) if costs else 0,
            "cacheHitRate": (cacheHits / total) * 100 if total > 0 else 0,
            "cacheHits": cacheHits,
            "cacheMisses": total - cacheHits,
        }

    def _percentile(self, sortedValues: list[float], percentile: int) -> float:
        """Calculate percentile from sorted values."""
        if not sortedValues:
            return 0
        index = int(len(sortedValues) * percentile / 100)
        index = min(index, len(sortedValues) - 1)
        return sortedValues[index]

    def getAgentStats(self, agentName: str) -> dict[str, Any]:
        """Get statistics for a specific agent.

        Args:
            agentName: Agent to get stats for.

        Returns:
            Dictionary with agent-specific metrics.
        """
        agentMetrics = [m for m in self._interactions if m.agentName == agentName]

        if not agentMetrics:
            return {
                "agentName": agentName,
                "totalInteractions": 0,
                "avgResponseTimeMs": 0,
                "avgCost": 0,
                "cacheHitRate": 0,
            }

        times = [m.responseTimeMs for m in agentMetrics]
        costs = [m.cost for m in agentMetrics]
        cacheHits = sum(1 for m in agentMetrics if m.fromCache)
        total = len(agentMetrics)

        return {
            "agentName": agentName,
            "totalInteractions": total,
            "avgResponseTimeMs": mean(times),
            "avgCost": mean(costs) if costs else 0,
            "totalCost": sum(costs),
            "cacheHitRate": (cacheHits / total) * 100 if total > 0 else 0,
        }

    def createBaseline(self, name: str) -> PerformanceBaseline:
        """Create a performance baseline from current metrics.

        Args:
            name: Name for the baseline.

        Returns:
            Created PerformanceBaseline.
        """
        stats = self.getStats()

        baseline = PerformanceBaseline(
            name=name,
            avgResponseTimeMs=stats["avgResponseTimeMs"],
            p95ResponseTimeMs=stats["p95ResponseTimeMs"],
            avgCostPerInteraction=stats["avgCostPerInteraction"],
            cacheHitRate=stats["cacheHitRate"],
            totalInteractions=stats["totalInteractions"],
        )

        self._baselines[name] = baseline
        logger.info(f"Created baseline: {name}")

        return baseline

    def compareToBaseline(self, baselineName: str) -> dict[str, Any]:
        """Compare current performance to a baseline.

        Args:
            baselineName: Name of baseline to compare against.

        Returns:
            Comparison results with regression indicators.
        """
        if baselineName not in self._baselines:
            raise ValueError(f"Baseline '{baselineName}' not found")

        baseline = self._baselines[baselineName]
        current = self.getStats()

        # Calculate deltas
        responseTimeDelta = current["avgResponseTimeMs"] - baseline.avgResponseTimeMs
        costDelta = current["avgCostPerInteraction"] - baseline.avgCostPerInteraction
        cacheRateDelta = current["cacheHitRate"] - baseline.cacheHitRate

        # Determine regressions (>10% worse is a regression)
        responseTimeRegression = (
            responseTimeDelta / baseline.avgResponseTimeMs > 0.1
            if baseline.avgResponseTimeMs > 0
            else False
        )
        costRegression = (
            costDelta / baseline.avgCostPerInteraction > 0.1
            if baseline.avgCostPerInteraction > 0
            else False
        )
        cacheRateRegression = cacheRateDelta < -5  # 5% drop in cache rate

        return {
            "baseline": baseline.name,
            "current": {
                "avgResponseTimeMs": current["avgResponseTimeMs"],
                "avgCostPerInteraction": current["avgCostPerInteraction"],
                "cacheHitRate": current["cacheHitRate"],
                "totalInteractions": current["totalInteractions"],
            },
            "baseline_values": {
                "avgResponseTimeMs": baseline.avgResponseTimeMs,
                "avgCostPerInteraction": baseline.avgCostPerInteraction,
                "cacheHitRate": baseline.cacheHitRate,
                "totalInteractions": baseline.totalInteractions,
            },
            "deltas": {
                "responseTimeMs": responseTimeDelta,
                "costPerInteraction": costDelta,
                "cacheHitRate": cacheRateDelta,
            },
            "regressions": {
                "responseTime": responseTimeRegression,
                "cost": costRegression,
                "cacheRate": cacheRateRegression,
                "any": responseTimeRegression or costRegression or cacheRateRegression,
            },
        }

    def hasRegression(self, baselineName: str) -> bool:
        """Check if there's any regression compared to baseline.

        Args:
            baselineName: Baseline to compare against.

        Returns:
            True if any regression detected.
        """
        comparison = self.compareToBaseline(baselineName)
        return comparison["regressions"]["any"]

    def getRecentMetrics(self, count: int = 100) -> list[InteractionMetrics]:
        """Get recent interaction metrics.

        Args:
            count: Number of recent interactions to return.

        Returns:
            List of recent InteractionMetrics.
        """
        return self._interactions[-count:]

    def getBaselines(self) -> list[PerformanceBaseline]:
        """Get all saved baselines."""
        return list(self._baselines.values())

    def clear(self) -> None:
        """Clear all recorded metrics (not baselines)."""
        self._interactions.clear()
        logger.info("Cleared performance metrics")

    def clearBaselines(self) -> None:
        """Clear all baselines."""
        self._baselines.clear()
        logger.info("Cleared performance baselines")

    def formatReport(self) -> str:
        """Generate a human-readable performance report.

        Returns:
            Formatted performance report string.
        """
        stats = self.getStats()

        lines = [
            "Performance Report",
            "=" * 50,
            f"Total Interactions: {stats['totalInteractions']}",
            "",
            "Response Time:",
            f"  Average: {stats['avgResponseTimeMs']:.2f}ms",
            f"  P50: {stats['p50ResponseTimeMs']:.2f}ms",
            f"  P95: {stats['p95ResponseTimeMs']:.2f}ms",
            f"  P99: {stats['p99ResponseTimeMs']:.2f}ms",
            f"  Min: {stats['minResponseTimeMs']:.2f}ms",
            f"  Max: {stats['maxResponseTimeMs']:.2f}ms",
            "",
            "Cost:",
            f"  Total: ${stats['totalCost']:.6f}",
            f"  Per Interaction: ${stats['avgCostPerInteraction']:.6f}",
            "",
            "Cache Performance:",
            f"  Hit Rate: {stats['cacheHitRate']:.1f}%",
            f"  Hits: {stats['cacheHits']}",
            f"  Misses: {stats['cacheMisses']}",
        ]

        # Add baseline comparisons if any
        if self._baselines:
            lines.append("")
            lines.append("Baseline Comparisons:")
            for name in self._baselines:
                try:
                    comp = self.compareToBaseline(name)
                    status = "REGRESSION" if comp["regressions"]["any"] else "OK"
                    lines.append(f"  vs {name}: {status}")
                except Exception:
                    pass

        return "\n".join(lines)
