"""State bucketing for signature matching.

Buckets continuous values into ranges to enable response sharing
across similar (not identical) game states.
"""

from typing import Any

# Default bucket configurations
DEFAULT_BUCKETS = {
    "approval": [
        (0, 30, "very_low"),
        (30, 50, "low"),
        (50, 70, "medium"),
        (70, 85, "high"),
        (85, 100, "very_high"),
    ],
    "economy": [
        (-100, -50, "crisis"),
        (-50, -10, "recession"),
        (-10, 10, "stable"),
        (10, 50, "growing"),
        (50, 100, "booming"),
    ],
    "tension": [
        (0, 25, "calm"),
        (25, 50, "uneasy"),
        (50, 75, "tense"),
        (75, 100, "critical"),
    ],
}


def bucketValue(value: float, buckets: list[tuple[float, float, str]]) -> str:
    """Bucket a numeric value into a category.

    Args:
        value: The numeric value to bucket.
        buckets: List of (min, max, label) tuples.

    Returns:
        The bucket label, or "unknown" if no match.

    Example:
        >>> buckets = [(0, 50, "low"), (50, 100, "high")]
        >>> bucketValue(25, buckets)
        'low'
        >>> bucketValue(75, buckets)
        'high'
    """
    for minVal, maxVal, label in buckets:
        if minVal <= value < maxVal:
            return label

    # Handle edge case: value equals max of last bucket
    if buckets and value == buckets[-1][1]:
        return buckets[-1][2]

    return "unknown"


def bucketState(
    state: dict[str, Any],
    bucketConfig: dict[str, list[tuple[float, float, str]]] | None = None,
) -> str:
    """Bucket all state values into a signature-friendly string.

    Args:
        state: Dictionary of state key to numeric value.
        bucketConfig: Custom bucket configuration (optional).

    Returns:
        Comma-separated string of key:bucket pairs.

    Example:
        >>> state = {"approval": 67, "economy": 5}
        >>> bucketState(state)
        'approval:medium,economy:stable'
    """
    config = bucketConfig or DEFAULT_BUCKETS
    parts: list[str] = []

    for key in sorted(state.keys()):
        value = state[key]

        if isinstance(value, (int, float)) and key in config:
            bucket = bucketValue(value, config[key])
            parts.append(f"{key}:{bucket}")
        elif isinstance(value, str):
            # String values are used directly (lowercase)
            parts.append(f"{key}:{value.lower()}")
        elif isinstance(value, bool):
            # Boolean values
            parts.append(f"{key}:{str(value).lower()}")

    return ",".join(parts)


def createBucketConfig(
    key: str,
    ranges: list[tuple[float, float, str]],
) -> dict[str, list[tuple[float, float, str]]]:
    """Create a bucket configuration for a single key.

    Args:
        key: The state key to bucket.
        ranges: List of (min, max, label) tuples.

    Returns:
        Bucket configuration dictionary.
    """
    return {key: ranges}


def mergeBucketConfigs(
    *configs: dict[str, list[tuple[float, float, str]]],
) -> dict[str, list[tuple[float, float, str]]]:
    """Merge multiple bucket configurations.

    Args:
        *configs: Variable number of bucket configs to merge.

    Returns:
        Merged bucket configuration.
    """
    result: dict[str, list[tuple[float, float, str]]] = {}
    for config in configs:
        result.update(config)
    return result


class StateBucketer:
    """Stateful wrapper for state bucketing.

    Args:
        bucketConfig: Custom bucket configuration (optional).
    """

    def __init__(
        self,
        bucketConfig: dict[str, list[tuple[float, float, str]]] | None = None,
    ):
        self._config = bucketConfig or DEFAULT_BUCKETS.copy()

    def bucketState(self, state: dict[str, Any]) -> str:
        """Bucket all state values into a signature-friendly string.

        Args:
            state: Dictionary of state key to numeric value.

        Returns:
            Comma-separated string of key:bucket pairs.
        """
        return bucketState(state, self._config)

    def addBucketConfig(
        self,
        key: str,
        ranges: list[tuple[float, float, str]],
    ) -> None:
        """Add a bucket configuration for a key.

        Args:
            key: The state key to bucket.
            ranges: List of (min, max, label) tuples.
        """
        self._config[key] = ranges

    def getConfig(self) -> dict[str, list[tuple[float, float, str]]]:
        """Get the current bucket configuration."""
        return self._config.copy()
