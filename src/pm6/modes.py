"""Mode enumeration for LLM operation modes."""

from enum import Enum


class Mode(Enum):
    """Operating mode for LLM calls.

    Attributes:
        LIVE: Make real API calls and optionally log them.
        REPLAY: Use logged responses instead of API calls.
        HYBRID: Try replay first, fall back to live if not found.
    """

    LIVE = "LIVE"
    REPLAY = "REPLAY"
    HYBRID = "HYBRID"
