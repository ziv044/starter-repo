"""Transaction support for atomic operations.

Provides transaction management with automatic rollback on failure,
state snapshots, and recovery capabilities.

NFR11-13: Transactions, Crash Recovery, State Consistency
"""

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Generator

logger = logging.getLogger("pm6.reliability")


class TransactionState(Enum):
    """State of a transaction."""

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class TransactionError(Exception):
    """Error during transaction execution."""

    pass


@dataclass
class StateSnapshot:
    """Snapshot of simulation state at a point in time.

    Used for rollback and recovery operations.

    Attributes:
        timestamp: When snapshot was created.
        worldState: Copy of world state.
        agentStates: Copy of agent configurations.
        turnCount: Turn count at snapshot.
        history: Copy of interaction history.
        metadata: Additional snapshot metadata.
    """

    timestamp: datetime
    worldState: dict[str, Any]
    agentStates: dict[str, dict[str, Any]]
    turnCount: int
    history: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "worldState": self.worldState,
            "agentStates": self.agentStates,
            "turnCount": self.turnCount,
            "history": self.history,
            "metadata": self.metadata,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> "StateSnapshot":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            worldState=data["worldState"],
            agentStates=data["agentStates"],
            turnCount=data["turnCount"],
            history=data["history"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class Transaction:
    """A transaction for atomic operations.

    Attributes:
        id: Unique transaction identifier.
        state: Current transaction state.
        snapshot: State snapshot for rollback.
        operations: List of operations performed.
        startTime: When transaction started.
        endTime: When transaction ended.
        error: Error if transaction failed.
    """

    id: str
    state: TransactionState = TransactionState.PENDING
    snapshot: StateSnapshot | None = None
    operations: list[dict[str, Any]] = field(default_factory=list)
    startTime: datetime | None = None
    endTime: datetime | None = None
    error: str | None = None

    def recordOperation(self, operationType: str, details: dict[str, Any]) -> None:
        """Record an operation performed in this transaction."""
        self.operations.append({
            "type": operationType,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        })

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "state": self.state.value,
            "startTime": self.startTime.isoformat() if self.startTime else None,
            "endTime": self.endTime.isoformat() if self.endTime else None,
            "operations": self.operations,
            "error": self.error,
        }


class TransactionManager:
    """Manages transactions for atomic operations.

    Provides transaction support with automatic rollback on failure,
    ensuring state consistency even when operations fail.

    Args:
        snapshotProvider: Callable that returns current state snapshot.
        stateRestorer: Callable that restores state from snapshot.
        autoSaveInterval: Number of operations before auto-checkpoint.

    Example:
        >>> manager = TransactionManager(sim.createSnapshot, sim.restoreSnapshot)
        >>> with manager.transaction() as tx:
        ...     sim.interact("pm", "Hello")
        ...     sim.interact("chancellor", "Budget?")
        ...     tx.recordOperation("batch_interaction", {"count": 2})
    """

    def __init__(
        self,
        snapshotProvider: Callable[[], StateSnapshot],
        stateRestorer: Callable[[StateSnapshot], None],
        autoSaveInterval: int = 0,
    ):
        self._snapshotProvider = snapshotProvider
        self._stateRestorer = stateRestorer
        self._autoSaveInterval = autoSaveInterval

        self._currentTransaction: Transaction | None = None
        self._transactionHistory: list[Transaction] = []
        self._operationCount = 0
        self._lastAutoSave: StateSnapshot | None = None

        self._transactionCounter = 0

    def _generateId(self) -> str:
        """Generate unique transaction ID."""
        self._transactionCounter += 1
        return f"tx_{self._transactionCounter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    @contextmanager
    def transaction(self) -> Generator[Transaction, None, None]:
        """Context manager for transactional operations.

        Creates a state snapshot, executes operations, and automatically
        rolls back on exception.

        Yields:
            Transaction object for recording operations.

        Raises:
            TransactionError: If already in a transaction.

        Example:
            >>> with manager.transaction() as tx:
            ...     # Operations here are atomic
            ...     sim.interact("pm", "Hello")
            ...     if error_condition:
            ...         raise ValueError("Rollback needed")
        """
        if self._currentTransaction is not None:
            raise TransactionError("Already in a transaction")

        # Create transaction
        tx = Transaction(
            id=self._generateId(),
            startTime=datetime.now(),
        )
        tx.state = TransactionState.ACTIVE

        # Capture snapshot for rollback
        try:
            tx.snapshot = self._snapshotProvider()
        except Exception as e:
            tx.state = TransactionState.FAILED
            tx.error = f"Failed to capture snapshot: {e}"
            raise TransactionError(tx.error) from e

        self._currentTransaction = tx
        logger.debug(f"Started transaction: {tx.id}")

        try:
            yield tx

            # Commit on success
            tx.state = TransactionState.COMMITTED
            tx.endTime = datetime.now()
            logger.debug(f"Committed transaction: {tx.id}")

        except Exception as e:
            # Rollback on failure
            tx.state = TransactionState.ROLLED_BACK
            tx.error = str(e)
            tx.endTime = datetime.now()

            if tx.snapshot:
                try:
                    self._stateRestorer(tx.snapshot)
                    logger.info(f"Rolled back transaction: {tx.id}")
                except Exception as restore_error:
                    tx.state = TransactionState.FAILED
                    tx.error = f"Rollback failed: {restore_error}"
                    logger.error(f"Failed to rollback: {restore_error}")
                    raise TransactionError(tx.error) from restore_error

            raise

        finally:
            self._transactionHistory.append(tx)
            self._currentTransaction = None

    def execute(
        self,
        operation: Callable[[], Any],
        operationType: str = "operation",
    ) -> Any:
        """Execute a single operation in a transaction.

        Args:
            operation: Callable to execute.
            operationType: Type name for logging.

        Returns:
            Result of the operation.
        """
        with self.transaction() as tx:
            result = operation()
            tx.recordOperation(operationType, {"result": str(result)[:100]})
            return result

    def executeMany(
        self,
        operations: list[tuple[Callable[[], Any], str]],
    ) -> list[Any]:
        """Execute multiple operations in a single transaction.

        Args:
            operations: List of (callable, type_name) tuples.

        Returns:
            List of results from each operation.
        """
        results = []
        with self.transaction() as tx:
            for operation, opType in operations:
                result = operation()
                tx.recordOperation(opType, {"result": str(result)[:100]})
                results.append(result)
        return results

    def checkpoint(self) -> StateSnapshot:
        """Create a manual checkpoint of current state.

        Returns:
            StateSnapshot of current state.
        """
        snapshot = self._snapshotProvider()
        self._lastAutoSave = snapshot
        logger.debug("Created checkpoint")
        return snapshot

    def restoreCheckpoint(self, snapshot: StateSnapshot) -> None:
        """Restore state from a checkpoint.

        Args:
            snapshot: Snapshot to restore.
        """
        self._stateRestorer(snapshot)
        logger.info("Restored from checkpoint")

    def getTransactionHistory(self) -> list[Transaction]:
        """Get history of transactions.

        Returns:
            List of completed transactions.
        """
        return list(self._transactionHistory)

    def getLastSuccessful(self) -> Transaction | None:
        """Get the last successfully committed transaction.

        Returns:
            Last committed transaction or None.
        """
        for tx in reversed(self._transactionHistory):
            if tx.state == TransactionState.COMMITTED:
                return tx
        return None

    def getFailedTransactions(self) -> list[Transaction]:
        """Get all failed or rolled-back transactions.

        Returns:
            List of failed transactions.
        """
        return [
            tx for tx in self._transactionHistory
            if tx.state in (TransactionState.FAILED, TransactionState.ROLLED_BACK)
        ]

    def clearHistory(self) -> None:
        """Clear transaction history."""
        self._transactionHistory.clear()

    @property
    def isInTransaction(self) -> bool:
        """Check if currently in a transaction."""
        return self._currentTransaction is not None

    @property
    def currentTransaction(self) -> Transaction | None:
        """Get current transaction if any."""
        return self._currentTransaction

    def getStats(self) -> dict[str, Any]:
        """Get transaction statistics.

        Returns:
            Dictionary with statistics.
        """
        committed = sum(
            1 for tx in self._transactionHistory
            if tx.state == TransactionState.COMMITTED
        )
        rolledBack = sum(
            1 for tx in self._transactionHistory
            if tx.state == TransactionState.ROLLED_BACK
        )
        failed = sum(
            1 for tx in self._transactionHistory
            if tx.state == TransactionState.FAILED
        )

        return {
            "totalTransactions": len(self._transactionHistory),
            "committed": committed,
            "rolledBack": rolledBack,
            "failed": failed,
            "successRate": committed / len(self._transactionHistory)
            if self._transactionHistory else 1.0,
        }
