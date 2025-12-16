"""Event bus for simulation event handling.

Provides a pub/sub event system for agents to react to changes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

from pm6.core.types import Event

logger = logging.getLogger("pm6.core.events")


EventHandler = Callable[[Event], None]


class EventBus:
    """Publish/subscribe event bus for simulation events.

    Allows components to subscribe to events and react to changes
    in the simulation.

    Example:
        >>> bus = EventBus()
        >>> bus.subscribe("state_changed", lambda e: print(f"State changed: {e.data}"))
        >>> bus.emit("state_changed", {"key": "value"})
        State changed: {'key': 'value'}
    """

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._agentSubscriptions: dict[str, set[str]] = defaultdict(set)
        self._eventHistory: list[Event] = []
        self._maxHistory = 100

    def subscribe(self, eventName: str, handler: EventHandler) -> None:
        """Subscribe to an event.

        Args:
            eventName: Event name to subscribe to (supports wildcards with '*').
            handler: Callback function receiving Event.
        """
        self._handlers[eventName].append(handler)
        logger.debug(f"Subscribed handler to '{eventName}'")

    def unsubscribe(self, eventName: str, handler: EventHandler) -> bool:
        """Unsubscribe a handler from an event.

        Args:
            eventName: Event name.
            handler: Handler to remove.

        Returns:
            True if handler was found and removed.
        """
        if eventName in self._handlers and handler in self._handlers[eventName]:
            self._handlers[eventName].remove(handler)
            return True
        return False

    def subscribeAgent(self, agentName: str, eventNames: list[str]) -> None:
        """Subscribe an agent to multiple events.

        Args:
            agentName: Name of the agent.
            eventNames: List of event names to subscribe to.
        """
        self._agentSubscriptions[agentName].update(eventNames)
        logger.debug(f"Agent '{agentName}' subscribed to: {eventNames}")

    def unsubscribeAgent(self, agentName: str, eventName: str | None = None) -> None:
        """Unsubscribe an agent from events.

        Args:
            agentName: Name of the agent.
            eventName: Specific event (None = all events).
        """
        if eventName is None:
            self._agentSubscriptions.pop(agentName, None)
        elif agentName in self._agentSubscriptions:
            self._agentSubscriptions[agentName].discard(eventName)

    def getAgentSubscriptions(self, agentName: str) -> set[str]:
        """Get events an agent is subscribed to.

        Args:
            agentName: Name of the agent.

        Returns:
            Set of event names.
        """
        return self._agentSubscriptions.get(agentName, set())

    def isAgentSubscribed(self, agentName: str, eventName: str) -> bool:
        """Check if an agent is subscribed to an event.

        Args:
            agentName: Name of the agent.
            eventName: Event name.

        Returns:
            True if agent is subscribed.
        """
        return eventName in self._agentSubscriptions.get(agentName, set())

    def emit(
        self,
        eventName: str,
        data: dict[str, Any] | None = None,
        source: str = "system",
    ) -> Event:
        """Emit an event to all subscribers.

        Args:
            eventName: Name of the event.
            data: Event data payload.
            source: Source of the event.

        Returns:
            The Event that was emitted.
        """
        event = Event(name=eventName, data=data or {}, source=source)
        return self.emitEvent(event)

    def emitEvent(self, event: Event) -> Event:
        """Emit an Event object to all subscribers.

        Args:
            event: Event to emit.

        Returns:
            The Event that was emitted.
        """
        # Add to history
        self._eventHistory.append(event)
        if len(self._eventHistory) > self._maxHistory:
            self._eventHistory.pop(0)

        # Get matching handlers
        handlers = self._getMatchingHandlers(event.name)

        # Call handlers
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error for '{event.name}': {e}")

        logger.debug(f"Emitted event '{event.name}' to {len(handlers)} handlers")
        return event

    def _getMatchingHandlers(self, eventName: str) -> list[EventHandler]:
        """Get all handlers matching an event name.

        Supports exact matches and wildcard patterns.

        Args:
            eventName: Event name to match.

        Returns:
            List of matching handlers.
        """
        handlers: list[EventHandler] = []

        # Exact match
        handlers.extend(self._handlers.get(eventName, []))

        # Wildcard match (e.g., "state_changed.*" matches "state_changed.health")
        for pattern, pattern_handlers in self._handlers.items():
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if eventName.startswith(prefix):
                    handlers.extend(pattern_handlers)
            elif pattern == "*":
                handlers.extend(pattern_handlers)

        return handlers

    def getSubscribedAgents(self, eventName: str) -> list[str]:
        """Get all agents subscribed to an event.

        Args:
            eventName: Event name.

        Returns:
            List of agent names.
        """
        agents = []
        for agentName, events in self._agentSubscriptions.items():
            if eventName in events:
                agents.append(agentName)
        return agents

    def getHistory(self, limit: int = 10) -> list[Event]:
        """Get recent event history.

        Args:
            limit: Maximum events to return.

        Returns:
            List of recent events (newest last).
        """
        return self._eventHistory[-limit:]

    def clearHistory(self) -> None:
        """Clear event history."""
        self._eventHistory.clear()

    def clear(self) -> None:
        """Clear all handlers and subscriptions."""
        self._handlers.clear()
        self._agentSubscriptions.clear()
        self._eventHistory.clear()

    def getStats(self) -> dict[str, Any]:
        """Get event bus statistics.

        Returns:
            Dictionary with stats.
        """
        return {
            "totalHandlers": sum(len(h) for h in self._handlers.values()),
            "eventTypes": len(self._handlers),
            "subscribedAgents": len(self._agentSubscriptions),
            "historySize": len(self._eventHistory),
        }


# Standard event names
class Events:
    """Standard event name constants."""

    # Turn events
    TURN_START = "turn_start"
    TURN_END = "turn_end"

    # Agent events
    AGENT_SPOKE = "agent_spoke"
    AGENT_ACTED = "agent_acted"
    PLAYER_ACTION = "player_action"

    # State events
    STATE_CHANGED = "state_changed"

    # Simulation lifecycle
    SIMULATION_START = "simulation_start"
    SIMULATION_END = "simulation_end"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CHECKPOINT_LOADED = "checkpoint_loaded"
