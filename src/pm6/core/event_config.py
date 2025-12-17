"""Event configuration for Play Mode.

Defines event structures with pre-scripted choices and impacts,
enabling a rich player experience without additional LLM calls.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("pm6.core.event_config")


@dataclass
class ChoiceConfig:
    """Configuration for a player choice option.

    Attributes:
        id: Unique identifier (e.g., "A", "B", "C", "D").
        text: Display text for the choice.
        impacts: Pre-computed state changes when this choice is selected.
    """

    id: str
    text: str
    impacts: dict[str, int | float] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "impacts": self.impacts,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> ChoiceConfig:
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            impacts=data.get("impacts", {}),
        )


@dataclass
class EventConfig:
    """Configuration for a simulation event with narrative and choices.

    Events can be:
    - Scheduled for specific turns
    - Triggered by player choices
    - Chained via nextEventMapping

    Attributes:
        name: Unique event identifier.
        turn: Turn number when event fires (0 = immediate, -1 = triggered only).
        narrative: Story text to display when event fires.
        choices: List of player choice options.
        nextEventMapping: Maps choice_id to next event name.
        metadata: Additional event data.
    """

    name: str
    turn: int = 1
    narrative: str = ""
    choices: list[ChoiceConfig] = field(default_factory=list)
    nextEventMapping: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "turn": self.turn,
            "narrative": self.narrative,
            "choices": [c.toDict() for c in self.choices],
            "nextEventMapping": self.nextEventMapping,
            "metadata": self.metadata,
        }

    @classmethod
    def fromDict(cls, data: dict[str, Any]) -> EventConfig:
        """Create from dictionary."""
        choices = [
            ChoiceConfig.fromDict(c) if isinstance(c, dict) else c
            for c in data.get("choices", [])
        ]
        return cls(
            name=data.get("name", ""),
            turn=data.get("turn", 1),
            narrative=data.get("narrative", ""),
            choices=choices,
            nextEventMapping=data.get("nextEventMapping", {}),
            metadata=data.get("metadata", {}),
        )

    def toEventData(self) -> dict[str, Any]:
        """Convert to event data format for the engine.

        This format is expected by the choice generator.
        """
        return {
            "narrative": self.narrative,
            "choices": [
                {
                    "id": c.id,
                    "text": c.text,
                    "impacts": c.impacts,
                }
                for c in self.choices
            ],
            "nextEventMapping": self.nextEventMapping,
            **self.metadata,
        }

    def getNextEvent(self, choiceId: str) -> str | None:
        """Get the next event name for a given choice.

        Args:
            choiceId: The selected choice ID.

        Returns:
            Next event name or None if not mapped.
        """
        return self.nextEventMapping.get(choiceId)


class EventConfigStore:
    """Storage and retrieval for event configurations.

    Manages event configs stored as JSON files in a directory structure:
    db/{sim_name}/events/{event_name}.json
    """

    def __init__(self, eventsPath: Path) -> None:
        """Initialize the event config store.

        Args:
            eventsPath: Path to the events directory.
        """
        self._eventsPath = eventsPath
        self._cache: dict[str, EventConfig] = {}

    @property
    def eventsPath(self) -> Path:
        """Get the events directory path."""
        return self._eventsPath

    def load(self, name: str) -> EventConfig | None:
        """Load an event config by name.

        Args:
            name: Event name (without .json extension).

        Returns:
            EventConfig or None if not found.
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        # Load from file
        eventFile = self._eventsPath / f"{name}.json"
        if not eventFile.exists():
            logger.debug(f"Event config not found: {eventFile}")
            return None

        try:
            with open(eventFile, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = EventConfig.fromDict(data)
            self._cache[name] = config
            logger.debug(f"Loaded event config: {name}")
            return config
        except Exception as e:
            logger.error(f"Failed to load event config {name}: {e}")
            return None

    def save(self, config: EventConfig) -> bool:
        """Save an event config to disk.

        Args:
            config: EventConfig to save.

        Returns:
            True if saved successfully.
        """
        self._eventsPath.mkdir(parents=True, exist_ok=True)
        eventFile = self._eventsPath / f"{config.name}.json"

        try:
            with open(eventFile, "w", encoding="utf-8") as f:
                json.dump(config.toDict(), f, indent=2)
            self._cache[config.name] = config
            logger.debug(f"Saved event config: {config.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save event config {config.name}: {e}")
            return False

    def list(self) -> list[str]:
        """List all available event configs.

        Returns:
            List of event names.
        """
        if not self._eventsPath.exists():
            return []

        names = []
        for f in self._eventsPath.glob("*.json"):
            names.append(f.stem)
        return sorted(names)

    def exists(self, name: str) -> bool:
        """Check if an event config exists.

        Args:
            name: Event name.

        Returns:
            True if the event config exists.
        """
        if name in self._cache:
            return True
        return (self._eventsPath / f"{name}.json").exists()

    def delete(self, name: str) -> bool:
        """Delete an event config.

        Args:
            name: Event name to delete.

        Returns:
            True if deleted successfully.
        """
        eventFile = self._eventsPath / f"{name}.json"
        if eventFile.exists():
            try:
                eventFile.unlink()
                self._cache.pop(name, None)
                logger.debug(f"Deleted event config: {name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete event config {name}: {e}")
                return False
        return False

    def clearCache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
