"""CLI entry point for pm6.

Usage:
    python -m pm6 run <simulation_name>    Run an interactive simulation
    python -m pm6 list                     List available simulations
    python -m pm6 create <name>            Create a new simulation template
    python -m pm6 info <simulation_name>   Show simulation details
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pm6",
        description="PM6 Simulation Engine - Run LLM-powered simulations",
    )
    parser.add_argument(
        "--simulations-dir",
        type=Path,
        default=None,
        help="Path to simulations directory (default: ./simulations)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to database storage (default: ./db)",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode with mock responses",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    runParser = subparsers.add_parser("run", help="Run an interactive simulation")
    runParser.add_argument("simulation", help="Name of the simulation to run")
    runParser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Default agent to interact with",
    )

    # list command
    subparsers.add_parser("list", help="List available simulations")

    # create command
    createParser = subparsers.add_parser("create", help="Create a new simulation template")
    createParser.add_argument("name", help="Name for the new simulation")
    createParser.add_argument(
        "--description",
        type=str,
        default="",
        help="Description for the simulation",
    )

    # info command
    infoParser = subparsers.add_parser("info", help="Show simulation details")
    infoParser.add_argument("simulation", help="Name of the simulation")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "run":
            return cmdRun(args)
        elif args.command == "list":
            return cmdList(args)
        elif args.command == "create":
            return cmdCreate(args)
        elif args.command == "info":
            return cmdInfo(args)
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def cmdRun(args: argparse.Namespace) -> int:
    """Run an interactive simulation."""
    from pm6.cli.loader import SimulationLoader
    from pm6.cli.runner import SimulationRunner

    loader = SimulationLoader(args.simulations_dir)

    # Check if simulation exists
    if args.simulation not in loader.listSimulations():
        print(f"Simulation '{args.simulation}' not found.")
        available = loader.listSimulations()
        if available:
            print(f"Available simulations: {', '.join(available)}")
        else:
            print(f"No simulations found in {loader.simulationsDir}")
            print("Create one with: python -m pm6 create <name>")
        return 1

    # Load and run
    runner = SimulationRunner(
        dbPath=args.db_path,
        testMode=args.test_mode,
    )
    runner.load(args.simulation, args.simulations_dir)
    runner.runInteractive(defaultAgent=args.agent)

    return 0


def cmdList(args: argparse.Namespace) -> int:
    """List available simulations."""
    from pm6.cli.loader import SimulationLoader

    loader = SimulationLoader(args.simulations_dir)
    simulations = loader.listSimulations()

    if not simulations:
        print(f"No simulations found in {loader.simulationsDir}")
        print("Create one with: python -m pm6 create <name>")
        return 0

    print(f"\nAvailable simulations ({loader.simulationsDir}):\n")

    for name in simulations:
        try:
            config = loader.load(name)
            agentCount = len(config.agents)
            desc = config.description[:50] + "..." if len(config.description) > 50 else config.description
            print(f"  {name}")
            if desc:
                print(f"    {desc}")
            print(f"    Agents: {agentCount}")
        except Exception as e:
            print(f"  {name} (error: {e})")

    print()
    return 0


def cmdCreate(args: argparse.Namespace) -> int:
    """Create a new simulation template."""
    from pm6.cli.loader import SimulationLoader, SimulationConfig, AgentDefinition

    loader = SimulationLoader(args.simulations_dir)

    # Create default config
    config = SimulationConfig(
        name=args.name,
        description=args.description or f"Simulation: {args.name}",
        agents=[
            AgentDefinition(
                name="agent",
                role="Default Agent",
                systemPrompt="You are a helpful assistant in this simulation.",
            )
        ],
        initialState={
            "example_stat": 50,
        },
    )

    try:
        simPath = loader.createSimulation(args.name, config)
        print(f"Created simulation template: {simPath}")
        print(f"\nEdit {simPath / 'config.yaml'} to customize your simulation.")
        print(f"Run with: python -m pm6 run {args.name}")
    except FileExistsError:
        print(f"Simulation '{args.name}' already exists.")
        return 1

    return 0


def cmdInfo(args: argparse.Namespace) -> int:
    """Show simulation details."""
    from pm6.cli.loader import SimulationLoader

    loader = SimulationLoader(args.simulations_dir)

    try:
        config = loader.load(args.simulation)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    print(f"\n{'='*60}")
    print(f"  {config.name}")
    print(f"{'='*60}")

    if config.description:
        print(f"\n{config.description}")

    if config.author:
        print(f"\nAuthor: {config.author}")

    if config.tags:
        print(f"Tags: {', '.join(config.tags)}")

    print(f"\nAgents ({len(config.agents)}):")
    for agent in config.agents:
        print(f"  - {agent.name}: {agent.role}")
        print(f"    Model: {agent.model}")
        print(f"    Memory: {agent.memoryPolicy}")

    if config.initialState:
        print(f"\nInitial State:")
        for key, value in config.initialState.items():
            print(f"  {key}: {value}")

    if config.rules:
        print(f"\nRules ({len(config.rules)}):")
        for rule in config.rules:
            print(f"  - {rule.type}: {rule.name or '(unnamed)'}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
