"""Response caching for pre-generated responses.

Stores multiple responses per signature to enable variety
while still benefiting from caching.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger("pm6.cost")


class CachedResponse:
    """A cached response for a signature.

    Attributes:
        signature: The signature this response is for.
        response: The response content.
        metadata: Additional response metadata (cost, latency, etc.).
    """

    def __init__(
        self,
        signature: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.signature = signature
        self.response = response
        self.metadata = metadata or {}

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "signature": self.signature,
            "response": self.response,
            "metadata": self.metadata,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "CachedResponse":
        """Create from dictionary."""
        return cls(
            signature=data["signature"],
            response=data["response"],
            metadata=data.get("metadata", {}),
        )


class ResponseCache:
    """Cache for pre-generated responses.

    Supports multiple responses per signature for variety.
    Responses are stored in a folder-based structure.

    Args:
        basePath: Base directory for cache storage.
        maxResponsesPerSignature: Maximum responses to store per signature.
    """

    def __init__(
        self,
        basePath: Path,
        maxResponsesPerSignature: int = 5,
    ):
        self.basePath = basePath
        self.maxResponsesPerSignature = maxResponsesPerSignature
        self._ensurePath()

    def _ensurePath(self) -> None:
        """Ensure the cache directory exists."""
        self.basePath.mkdir(parents=True, exist_ok=True)

    def _getSignaturePath(self, signature: str) -> Path:
        """Get the path for a signature's cache file."""
        return self.basePath / f"{signature}.json"

    def get(self, signature: str) -> CachedResponse | None:
        """Get a random cached response for a signature.

        Args:
            signature: The request signature.

        Returns:
            A cached response if found, None otherwise.
        """
        path = self._getSignaturePath(signature)

        if not path.exists():
            logger.debug(f"Cache miss: {signature}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            responses = data.get("responses", [])
            if not responses:
                return None

            # Select random response for variety
            selected = random.choice(responses)
            logger.info(f"Cache hit: {signature}")

            return CachedResponse.fromDict(selected)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Cache read error for {signature}: {e}")
            return None

    def put(self, cachedResponse: CachedResponse) -> None:
        """Store a response in the cache.

        Args:
            cachedResponse: The response to cache.
        """
        signature = cachedResponse.signature
        path = self._getSignaturePath(signature)

        # Load existing responses
        responses: list[dict[str, Any]] = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                responses = data.get("responses", [])
            except (json.JSONDecodeError, KeyError):
                responses = []

        # Add new response
        responses.append(cachedResponse.toDict())

        # Trim to max size (keep most recent)
        if len(responses) > self.maxResponsesPerSignature:
            responses = responses[-self.maxResponsesPerSignature :]

        # Save
        data = {"signature": signature, "responses": responses}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Cached response for {signature}")

    def has(self, signature: str) -> bool:
        """Check if a signature has cached responses.

        Args:
            signature: The request signature.

        Returns:
            True if cached responses exist.
        """
        path = self._getSignaturePath(signature)
        return path.exists()

    def clear(self) -> None:
        """Clear all cached responses."""
        for path in self.basePath.glob("*.json"):
            path.unlink()
        logger.info("Cache cleared")

    def getStats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        cacheFiles = list(self.basePath.glob("*.json"))
        totalResponses = 0

        for path in cacheFiles:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                totalResponses += len(data.get("responses", []))
            except (json.JSONDecodeError, KeyError):
                pass

        return {
            "signatures": len(cacheFiles),
            "totalResponses": totalResponses,
        }
