"""Reliability module for pm6.

Provides transaction support, crash recovery, and state consistency
features for robust simulation execution.

NFR11-15: Reliability Requirements Implementation
"""

from pm6.reliability.transactions import (
    StateSnapshot,
    Transaction,
    TransactionError,
    TransactionManager,
)

__all__ = [
    "Transaction",
    "TransactionManager",
    "TransactionError",
    "StateSnapshot",
]
