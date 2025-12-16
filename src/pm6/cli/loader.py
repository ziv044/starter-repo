"""Simulation configuration loader from YAML files."""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from pm6.agents.agentConfig import AgentConfig
from pm6.agents.memoryPolicy import MemoryPolicy
from pm6.core.rules import RuleType


class AgentDefinition(BaseModel):
    """Agent definition in simulation config."""

    name: str
    role: str
    systemPrompt: str
    model: str = "claude-sonnet-4-20250514"
    memoryPolicy: str = "SUMMARY"
    maxTurns: int = 10
    situationTypes: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    controlledBy: Literal["player", "cpu"] = "cpu"
    initiative: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def toAgentConfig(self) -> AgentConfig:
        """Convert to AgentConfig instance."""
        return AgentConfig(
            name=self.name,
            role=self.role,
            systemPrompt=self.systemPrompt,
            model=self.model,
            memoryPolicy=MemoryPolicy[self.memoryPolicy],
            maxTurns=self.maxTurns,
            situationTypes=self.situationTypes,
            tools=self.tools,
            controlledBy=self.controlledBy,
            initiative=self.initiative,
            metadata=self.metadata,
        )


class RuleDefinition(BaseModel):
    """Rule definition in simulation config."""

    type: str
    name: str = ""
    description: str = ""
    maxTurns: int | None = None
    maxCost: float | None = None
    condition: str | None = None


class SimulationConfig(BaseModel):
    """Simulation configuration loaded from YAML."""

    name: str
    description: str = ""
    agents: list[AgentDefinition]
    playerCharacter: str | None = Field(
        default=None,
        description="Name of the agent controlled by the player",
    )
    initialState: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleDefinition] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    version: str = "1.0"
    author: str = ""
    tags: list[str] = Field(default_factory=list)

    def getPlayerAgentName(self) -> str | None:
        """Get the name of the player-controlled agent.

        Returns playerCharacter if set, otherwise looks for agent with
        controlledBy='player', otherwise returns None.
        """
        if self.playerCharacter:
            return self.playerCharacter
        for agent in self.agents:
            if agent.controlledBy == "player":
                return agent.name
        return None


class SimulationLoader:
    """Loads simulation configurations from template folders."""

    DEFAULT_SIMULATIONS_DIR = "simulations"
    CONFIG_FILENAME = "config.yaml"

    def __init__(self, simulationsDir: Path | str | None = None):
        """Initialize loader with simulations directory.

        Args:
            simulationsDir: Path to simulations folder. Defaults to ./simulations
        """
        if simulationsDir is None:
            self._simulationsDir = Path.cwd() / self.DEFAULT_SIMULATIONS_DIR
        else:
            self._simulationsDir = Path(simulationsDir)

    @property
    def simulationsDir(self) -> Path:
        """Get the simulations directory path."""
        return self._simulationsDir

    def listSimulations(self) -> list[str]:
        """List all available simulation templates.

        Returns:
            List of simulation names (folder names).
        """
        if not self._simulationsDir.exists():
            return []

        simulations = []
        for folder in self._simulationsDir.iterdir():
            if folder.is_dir() and (folder / self.CONFIG_FILENAME).exists():
                simulations.append(folder.name)

        return sorted(simulations)

    def load(self, simulationName: str) -> SimulationConfig:
        """Load a simulation configuration by name.

        Args:
            simulationName: Name of the simulation (folder name).

        Returns:
            SimulationConfig instance.

        Raises:
            FileNotFoundError: If simulation or config not found.
            ValueError: If config is invalid.
        """
        simPath = self._simulationsDir / simulationName
        configPath = simPath / self.CONFIG_FILENAME

        if not simPath.exists():
            raise FileNotFoundError(f"Simulation '{simulationName}' not found at {simPath}")

        if not configPath.exists():
            raise FileNotFoundError(f"Config file not found at {configPath}")

        with open(configPath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle system prompt from external file
        for agent in data.get("agents", []):
            if "systemPromptFile" in agent:
                promptFile = simPath / agent["systemPromptFile"]
                if promptFile.exists():
                    agent["systemPrompt"] = promptFile.read_text(encoding="utf-8")
                del agent["systemPromptFile"]

        return SimulationConfig(**data)

    def loadFromPath(self, configPath: Path | str) -> SimulationConfig:
        """Load a simulation configuration from a specific file path.

        Args:
            configPath: Direct path to config.yaml file.

        Returns:
            SimulationConfig instance.
        """
        configPath = Path(configPath)

        if not configPath.exists():
            raise FileNotFoundError(f"Config file not found at {configPath}")

        with open(configPath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Handle system prompt from external file
        simPath = configPath.parent
        for agent in data.get("agents", []):
            if "systemPromptFile" in agent:
                promptFile = simPath / agent["systemPromptFile"]
                if promptFile.exists():
                    agent["systemPrompt"] = promptFile.read_text(encoding="utf-8")
                del agent["systemPromptFile"]

        return SimulationConfig(**data)

    def getSimulationPath(self, simulationName: str) -> Path:
        """Get the path to a simulation's folder.

        Args:
            simulationName: Name of the simulation.

        Returns:
            Path to the simulation folder.
        """
        return self._simulationsDir / simulationName

    def createSimulation(self, name: str, config: SimulationConfig | None = None) -> Path:
        """Create a new simulation template folder.

        Args:
            name: Name for the new simulation.
            config: Optional initial configuration.

        Returns:
            Path to the created simulation folder.

        Raises:
            FileExistsError: If simulation already exists.
        """
        simPath = self._simulationsDir / name

        if simPath.exists():
            raise FileExistsError(f"Simulation '{name}' already exists at {simPath}")

        # Create folder structure
        simPath.mkdir(parents=True)
        (simPath / "prompts").mkdir()

        # Create config
        if config is None:
            config = SimulationConfig(
                name=name,
                description=f"Simulation: {name}",
                agents=[
                    AgentDefinition(
                        name="agent",
                        role="Default Agent",
                        systemPrompt="You are a helpful assistant.",
                    )
                ],
            )

        # Write config
        configPath = simPath / self.CONFIG_FILENAME
        with open(configPath, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(exclude_none=True), f, default_flow_style=False, sort_keys=False)

        return simPath
