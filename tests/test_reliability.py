"""Tests for reliability module (NFR11-15)."""

import tempfile
from pathlib import Path

import pytest

from pm6 import AgentConfig, Simulation
from pm6.reliability import (
    StateSnapshot,
    Transaction,
    TransactionError,
    TransactionManager,
)
from pm6.reliability.transactions import TransactionState


class TestStateSnapshot:
    """Tests for StateSnapshot dataclass."""

    def test_create_snapshot(self):
        """Test creating a state snapshot."""
        from datetime import datetime

        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            worldState={"year": 2025},
            agentStates={"pm": {"name": "pm", "role": "PM"}},
            turnCount=5,
            history=[{"turn": 1}],
        )
        assert snapshot.worldState["year"] == 2025
        assert snapshot.turnCount == 5

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        from datetime import datetime

        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            worldState={"year": 2025},
            agentStates={},
            turnCount=0,
            history=[],
        )
        data = snapshot.toDict()
        assert "timestamp" in data
        assert data["worldState"]["year"] == 2025

    def test_snapshot_from_dict(self):
        """Test creating snapshot from dictionary."""
        data = {
            "timestamp": "2025-01-01T12:00:00",
            "worldState": {"year": 2025},
            "agentStates": {},
            "turnCount": 3,
            "history": [],
        }
        snapshot = StateSnapshot.fromDict(data)
        assert snapshot.turnCount == 3
        assert snapshot.worldState["year"] == 2025


class TestTransaction:
    """Tests for Transaction dataclass."""

    def test_create_transaction(self):
        """Test creating a transaction."""
        tx = Transaction(id="tx_1")
        assert tx.state == TransactionState.PENDING
        assert tx.snapshot is None
        assert tx.operations == []

    def test_record_operation(self):
        """Test recording an operation."""
        tx = Transaction(id="tx_1")
        tx.recordOperation("interact", {"agent": "pm"})
        assert len(tx.operations) == 1
        assert tx.operations[0]["type"] == "interact"

    def test_transaction_to_dict(self):
        """Test converting transaction to dictionary."""
        tx = Transaction(id="tx_1")
        tx.state = TransactionState.COMMITTED
        data = tx.toDict()
        assert data["id"] == "tx_1"
        assert data["state"] == "committed"


class TestTransactionManager:
    """Tests for TransactionManager."""

    def test_successful_transaction(self):
        """Test a successful transaction."""
        state = {"counter": 0}

        def create_snapshot():
            from datetime import datetime

            return StateSnapshot(
                timestamp=datetime.now(),
                worldState=state.copy(),
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            state.clear()
            state.update(snapshot.worldState)

        manager = TransactionManager(create_snapshot, restore_snapshot)

        with manager.transaction() as tx:
            state["counter"] = 1
            tx.recordOperation("increment", {"value": 1})

        assert state["counter"] == 1
        assert len(manager.getTransactionHistory()) == 1
        assert manager.getTransactionHistory()[0].state == TransactionState.COMMITTED

    def test_transaction_rollback(self):
        """Test transaction rollback on failure."""
        state = {"counter": 0}

        def create_snapshot():
            from datetime import datetime

            return StateSnapshot(
                timestamp=datetime.now(),
                worldState=state.copy(),
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            state.clear()
            state.update(snapshot.worldState)

        manager = TransactionManager(create_snapshot, restore_snapshot)

        with pytest.raises(ValueError):
            with manager.transaction() as tx:
                state["counter"] = 10
                raise ValueError("Simulated failure")

        # State should be rolled back
        assert state["counter"] == 0
        assert manager.getTransactionHistory()[0].state == TransactionState.ROLLED_BACK

    def test_nested_transaction_error(self):
        """Test that nested transactions raise error."""
        from datetime import datetime

        def create_snapshot():
            return StateSnapshot(
                timestamp=datetime.now(),
                worldState={},
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            pass

        manager = TransactionManager(create_snapshot, restore_snapshot)

        with pytest.raises(TransactionError):
            with manager.transaction():
                with manager.transaction():
                    pass

    def test_execute_single(self):
        """Test executing a single operation."""
        state = {"counter": 0}

        def create_snapshot():
            from datetime import datetime

            return StateSnapshot(
                timestamp=datetime.now(),
                worldState=state.copy(),
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            state.clear()
            state.update(snapshot.worldState)

        manager = TransactionManager(create_snapshot, restore_snapshot)

        def increment():
            state["counter"] += 1
            return state["counter"]

        result = manager.execute(increment, "increment")
        assert result == 1
        assert state["counter"] == 1

    def test_execute_many(self):
        """Test executing multiple operations."""
        state = {"counter": 0}

        def create_snapshot():
            from datetime import datetime

            return StateSnapshot(
                timestamp=datetime.now(),
                worldState=state.copy(),
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            state.clear()
            state.update(snapshot.worldState)

        manager = TransactionManager(create_snapshot, restore_snapshot)

        operations = [
            (lambda: state.update({"counter": state["counter"] + 1}) or state["counter"], "inc1"),
            (lambda: state.update({"counter": state["counter"] + 1}) or state["counter"], "inc2"),
        ]

        results = manager.executeMany(operations)
        assert len(results) == 2
        assert state["counter"] == 2

    def test_get_stats(self):
        """Test getting transaction statistics."""
        from datetime import datetime

        def create_snapshot():
            return StateSnapshot(
                timestamp=datetime.now(),
                worldState={},
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            pass

        manager = TransactionManager(create_snapshot, restore_snapshot)

        # Successful transaction
        with manager.transaction():
            pass

        # Failed transaction
        try:
            with manager.transaction():
                raise ValueError("fail")
        except ValueError:
            pass

        stats = manager.getStats()
        assert stats["totalTransactions"] == 2
        assert stats["committed"] == 1
        assert stats["rolledBack"] == 1

    def test_get_last_successful(self):
        """Test getting last successful transaction."""
        from datetime import datetime

        def create_snapshot():
            return StateSnapshot(
                timestamp=datetime.now(),
                worldState={},
                agentStates={},
                turnCount=0,
                history=[],
            )

        def restore_snapshot(snapshot):
            pass

        manager = TransactionManager(create_snapshot, restore_snapshot)

        with manager.transaction() as tx:
            tx.recordOperation("test", {})

        last = manager.getLastSuccessful()
        assert last is not None
        assert len(last.operations) == 1


class TestSimulationTransactions:
    """Tests for Simulation transaction integration."""

    def test_create_snapshot(self):
        """Test creating a simulation snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="Prime Minister")
            sim.registerAgent(agent)
            sim.setWorldState({"year": 2025})

            snapshot = sim.createSnapshot()

            assert snapshot.worldState["year"] == 2025
            assert "pm" in snapshot.agentStates

    def test_restore_snapshot(self):
        """Test restoring from a snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)
            sim.setWorldState({"status": "initial"})

            # Create snapshot
            snapshot = sim.createSnapshot()

            # Modify state
            sim.setWorldState({"status": "modified"})
            assert sim.getWorldState()["status"] == "modified"

            # Restore
            sim.restoreSnapshot(snapshot)
            assert sim.getWorldState()["status"] == "initial"

    def test_create_transaction_manager(self):
        """Test creating a transaction manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            manager = sim.createTransactionManager()

            assert manager is not None
            assert not manager.isInTransaction

    def test_execute_atomic(self):
        """Test atomic operation execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            sim.setWorldState({"counter": 0})

            def operation():
                current = sim.getWorldState()["counter"]
                sim.setWorldState({"counter": current + 1})
                return current + 1

            result = sim.executeAtomic(operation)
            assert result == 1
            assert sim.getWorldState()["counter"] == 1

    def test_execute_atomic_rollback(self):
        """Test atomic operation rollback on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            sim.setWorldState({"counter": 0})

            def failing_operation():
                sim.setWorldState({"counter": 999})
                raise ValueError("Simulated failure")

            with pytest.raises(ValueError):
                sim.executeAtomic(failing_operation)

            # Counter should be rolled back
            assert sim.getWorldState()["counter"] == 0

    def test_checkpoint_and_restore(self):
        """Test manual checkpoint and restore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            agent = AgentConfig(name="pm", role="PM")
            sim.registerAgent(agent)
            sim.setWorldState({"version": 1})

            # Create checkpoint
            checkpoint = sim.checkpoint()

            # Modify state
            sim.setWorldState({"version": 2})
            assert sim.getWorldState()["version"] == 2

            # Restore from checkpoint
            sim.restoreFromCheckpoint(checkpoint)
            assert sim.getWorldState()["version"] == 1

    def test_execute_many_atomic(self):
        """Test executing multiple operations atomically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sim = Simulation("test", dbPath=Path(tmpdir))
            sim.setWorldState({"a": 0, "b": 0})

            operations = [
                (
                    lambda: sim.setWorldState(
                        {**sim.getWorldState(), "a": 1}
                    ) or "a_set",
                    "set_a",
                ),
                (
                    lambda: sim.setWorldState(
                        {**sim.getWorldState(), "b": 2}
                    ) or "b_set",
                    "set_b",
                ),
            ]

            results = sim.executeManyAtomic(operations)
            assert len(results) == 2
            state = sim.getWorldState()
            assert state["a"] == 1
            assert state["b"] == 2
