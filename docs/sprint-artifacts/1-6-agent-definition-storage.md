# Story 1.6: Agent Definition & Storage

Status: done

## Story

As a **developer**,
I want **to define agents with configuration and persist them**,
so that **my simulation has characters/entities to interact with**.

## Acceptance Criteria

- [x] AC1: sim.registerAgent(AgentConfig(...)) adds agent
- [x] AC2: Agent config saved to ./db/my_sim/agents/name.json
- [x] AC3: sim.listAgents() returns agent names
- [x] AC4: sim.getAgent("name") returns AgentConfig

## Completion Notes

- **Brownfield**: Full AgentConfig and storage implemented
- Pydantic model with validation
- Supports: memoryPolicy, model, tools, controlledBy (player/cpu)
- Auto-loads existing agents on simulation init

## Files

- src/pm6/agents/agentConfig.py
- src/pm6/agents/memoryPolicy.py
- src/pm6/state/storage.py
