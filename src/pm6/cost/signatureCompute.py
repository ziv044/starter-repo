"""Signature computation using xxHash for fast, non-crypto hashing.

Signatures are used to identify similar requests that can share
pre-generated responses, reducing LLM calls.
"""

from dataclasses import dataclass
from typing import Any

import xxhash


@dataclass
class SignatureComponents:
    """Components that make up a request signature.

    Attributes:
        agentName: Name of the agent handling the request.
        situationType: Type of situation being handled.
        stateBucket: Bucketed state values (e.g., "approval:medium").
        inputIntent: Normalized user input.
    """

    agentName: str
    situationType: str
    stateBucket: str
    inputIntent: str


def computeSignature(components: SignatureComponents) -> str:
    """Compute a signature hash from components.

    Uses xxHash for fast, non-cryptographic hashing.
    The signature enables matching similar (not just identical) requests.

    Args:
        components: The signature components.

    Returns:
        Hex string of the signature hash.

    Example:
        >>> components = SignatureComponents(
        ...     agentName="prime_minister",
        ...     situationType="budget_crisis",
        ...     stateBucket="approval:medium,economy:struggling",
        ...     inputIntent="reduce defense spending"
        ... )
        >>> sig = computeSignature(components)
        >>> len(sig) == 16  # 64-bit hash as hex
        True
    """
    # Combine components into a single string
    combined = "|".join([
        components.agentName,
        components.situationType,
        components.stateBucket,
        components.inputIntent,
    ])

    # Compute xxHash64
    hashValue = xxhash.xxh64(combined.encode("utf-8")).hexdigest()

    return hashValue


def computeSignatureFromDict(data: dict[str, Any]) -> str:
    """Compute signature from a dictionary.

    Convenience method for computing signatures from raw data.

    Args:
        data: Dictionary with agentName, situationType, stateBucket, inputIntent.

    Returns:
        Hex string of the signature hash.
    """
    components = SignatureComponents(
        agentName=data.get("agentName", ""),
        situationType=data.get("situationType", ""),
        stateBucket=data.get("stateBucket", ""),
        inputIntent=data.get("inputIntent", ""),
    )
    return computeSignature(components)


def normalizeInput(userInput: str) -> str:
    """Normalize user input for signature matching.

    Performs basic normalization to increase cache hits
    while preserving semantic meaning.

    Args:
        userInput: Raw user input.

    Returns:
        Normalized input string.
    """
    # Basic normalization: lowercase, strip, collapse whitespace
    normalized = userInput.lower().strip()
    normalized = " ".join(normalized.split())

    return normalized
