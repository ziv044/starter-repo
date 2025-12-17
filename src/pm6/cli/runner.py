"""Interactive simulation runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pm6.cli.loader import SimulationConfig, SimulationLoader
from pm6.core.engine import SimulationEngine
from pm6.core.rules import Rule, RuleType
from pm6.core.simulation import Simulation


class SimulationRunner:
    """Runs interactive simulation sessions from configurations."""

    def __init__(
        self,
        dbPath: Path | str | None = None,
        testMode: bool = False,
    ):
        """Initialize the runner.

        Args:
            dbPath: Path for simulation database storage.
            testMode: Whether to run in test mode (mock responses).
        """
        self._dbPath = Path(dbPath) if dbPath else Path.cwd() / "db"
        self._testMode = testMode
        self._simulation: Simulation | None = None
        self._engine: SimulationEngine | None = None
        self._config: SimulationConfig | None = None

    def loadFromConfig(self, config: SimulationConfig) -> Simulation:
        """Create a simulation from a configuration.

        Args:
            config: SimulationConfig to load.

        Returns:
            Configured Simulation instance.
        """
        self._config = config

        # Create simulation
        sim = Simulation(
            name=config.name,
            dbPath=self._dbPath,
            testMode=self._testMode,
        )

        # Register agents
        for agentDef in config.agents:
            sim.registerAgent(agentDef.toAgentConfig())

        # Set player agent
        playerName = config.getPlayerAgentName()
        if playerName:
            sim.setPlayerAgent(playerName)

        # Set initial state
        if config.initialState:
            sim.setWorldState(config.initialState)

        # Add rules
        for ruleDef in config.rules:
            ruleType = RuleType[ruleDef.type]
            rule = Rule(
                ruleType=ruleType,
                name=ruleDef.name or f"{ruleDef.type}_rule",
                condition=lambda ctx: True,  # Default pass-through
                message=ruleDef.description or "",
            )
            sim.rules.addRule(rule)

        self._simulation = sim
        self._engine = SimulationEngine(sim)
        return sim

    def load(self, simulationName: str, simulationsDir: Path | str | None = None) -> Simulation:
        """Load and configure a simulation by name.

        Args:
            simulationName: Name of the simulation to load.
            simulationsDir: Optional custom simulations directory.

        Returns:
            Configured Simulation instance.
        """
        loader = SimulationLoader(simulationsDir)
        config = loader.load(simulationName)
        return self.loadFromConfig(config)

    def runInteractive(
        self,
        defaultAgent: str | None = None,
        welcomeMessage: str | None = None,
    ) -> None:
        """Run an interactive CLI session.

        Args:
            defaultAgent: Default agent to interact with.
            welcomeMessage: Custom welcome message.
        """
        if self._simulation is None:
            raise RuntimeError("No simulation loaded. Call load() first.")

        sim = self._simulation
        config = self._config

        # Determine default agent
        if defaultAgent is None and config and config.agents:
            defaultAgent = config.agents[0].name

        # Print welcome
        self._printWelcome(welcomeMessage)

        # Start simulation
        sim.start()

        try:
            self._interactiveLoop(sim, defaultAgent)
        except KeyboardInterrupt:
            print("\n\nSession interrupted.")
        finally:
            sim.stop()
            self._printStats(sim)

    def _printWelcome(self, customMessage: str | None = None) -> None:
        """Print welcome message and help."""
        if customMessage:
            print(customMessage)
        elif self._config:
            print(f"\n{'='*60}")
            print(f"  {self._config.name}")
            if self._config.description:
                print(f"  {self._config.description}")
            print(f"{'='*60}")
        else:
            print("\n" + "="*60)
            print("  PM6 Simulation")
            print("="*60)

        print("\nCommands:")
        print("  /quit, /exit  - End session")
        print("  /state        - Show current world state")
        print("  /agents       - List available agents")
        print("  /talk <agent> - Switch to talking with specific agent")
        print("  /save <name>  - Save checkpoint")
        print("  /load <name>  - Load checkpoint")
        print("  /history      - Show recent history")
        print("  /stats        - Show session statistics")
        print("  /help         - Show this help")
        print("\nTurn Control:")
        print("  /turn         - Show current turn number")
        print("  /step         - Advance one turn (CPU agents may act)")
        print("  /run [N]      - Auto-run N turns (default: until stopped)")
        print("  /pause        - Pause auto-run")
        print()

    def _interactiveLoop(self, sim: Simulation, currentAgent: str | None) -> None:
        """Main interactive loop."""
        while True:
            try:
                userInput = input(f"\n[{currentAgent}] > ").strip()
            except EOFError:
                break

            if not userInput:
                continue

            # Handle commands
            if userInput.startswith("/"):
                result = self._handleCommand(sim, userInput, currentAgent)
                if result == "quit":
                    break
                elif result and result.startswith("agent:"):
                    currentAgent = result.split(":")[1]
                continue

            # Regular interaction
            if currentAgent is None:
                print("No agent selected. Use /talk <agent> to select one.")
                continue

            try:
                response = sim.interact(currentAgent, userInput)
                print(f"\n{currentAgent}: {response.content}")
            except Exception as e:
                print(f"\nError: {e}")

    def _handleCommand(
        self,
        sim: Simulation,
        command: str,
        currentAgent: str | None,
    ) -> str | None:
        """Handle CLI commands.

        Returns:
            'quit' to exit, 'agent:<name>' to switch agent, None otherwise.
        """
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            return "quit"

        elif cmd == "state":
            state = sim.getWorldState()
            print("\nWorld State:")
            for key, value in state.items():
                print(f"  {key}: {value}")

        elif cmd == "agents":
            agents = sim.listAgents()
            print("\nAvailable Agents:")
            for name in agents:
                marker = " (current)" if name == currentAgent else ""
                agent = sim.getAgent(name)
                print(f"  {name}: {agent.role}{marker}")

        elif cmd == "talk":
            if not args:
                print("Usage: /talk <agent_name>")
            elif args not in sim.listAgents():
                print(f"Unknown agent: {args}")
                print(f"Available: {', '.join(sim.listAgents())}")
            else:
                print(f"Now talking to: {args}")
                return f"agent:{args}"

        elif cmd == "save":
            name = args or "quicksave"
            sim.saveCheckpoint(name)
            print(f"Saved checkpoint: {name}")

        elif cmd == "load":
            name = args or "quicksave"
            try:
                sim.loadCheckpoint(name)
                print(f"Loaded checkpoint: {name}")
            except Exception as e:
                print(f"Failed to load checkpoint: {e}")

        elif cmd == "history":
            history = sim.getHistory()
            count = min(5, len(history))
            print(f"\nRecent History (last {count}):")
            for interaction in history[-count:]:
                userPreview = interaction.userInput[:50] if interaction.userInput else ""
                responsePreview = interaction.response[:50] if interaction.response else ""
                print(f"  [{interaction.agentName}] User: {userPreview}...")
                print(f"             Agent: {responsePreview}...")

        elif cmd == "stats":
            self._printStats(sim)

        elif cmd == "help":
            self._printWelcome()

        # Turn control commands
        elif cmd == "turn":
            if self._engine:
                print(f"\nCurrent turn: {self._engine.currentTurn}")
            else:
                print("Engine not initialized")

        elif cmd == "step":
            if self._engine:
                result = self._engine.step()
                self._displayTurnResult(result)
            else:
                print("Engine not initialized")

        elif cmd == "run":
            if self._engine:
                try:
                    turns = int(args) if args else 5
                    print(f"\nRunning {turns} turns...")
                    results = self._engine.run(turns=turns, speed=0.5)
                    for result in results:
                        self._displayTurnResult(result)
                except ValueError:
                    print("Usage: /run [number_of_turns]")
            else:
                print("Engine not initialized")

        elif cmd == "pause":
            if self._engine:
                self._engine.pause()
                print("Simulation paused")
            else:
                print("Engine not initialized")

        else:
            print(f"Unknown command: {cmd}")
            print("Type /help for available commands.")

        return None

    def _displayTurnResult(self, result: Any) -> None:
        """Display the result of a turn.

        Args:
            result: TurnResult from engine.step()
        """
        print(f"\n[Turn {result.turnNumber}]")

        if result.cpuActions:
            for action in result.cpuActions:
                print(f"\n{action.agentName}: {action.content}")
        else:
            print("  (No CPU agent actions this turn)")

    def _printStats(self, sim: Simulation) -> None:
        """Print session statistics."""
        stats = sim.getStats()
        costs = stats.get("costs", {})
        tokenBudget = stats.get("tokenBudget", {})

        print("\nSession Statistics:")
        print(f"  Total interactions: {stats.get('turnCount', 0)}")
        print(f"  Cache hits: {costs.get('cacheHits', 0)}")
        print(f"  Total cost: ${costs.get('totalCost', 0):.4f}")
        print(f"  Tokens used: {tokenBudget.get('totalTokens', 0)}")
