# Story 1.5: Simulation Class & Basic CRUD

Status: done

## Story

As a **developer**,
I want **to create, load, and manage simulations via the Simulation class**,
so that **I can work with multiple simulation instances**.

## Acceptance Criteria

- [x] AC1: Simulation(name="my_sim") creates new simulation
- [x] AC2: Existing simulations load with preserved state
- [x] AC3: sim.getStats() returns turn count, agent count

## Completion Notes

- **Brownfield**: Comprehensive Simulation class implemented
- Features far exceed story requirements:
  - Full agent management
  - Response caching
  - Cost tracking
  - Session recording
  - Token budget management
  - Test mode support

## Files

- src/pm6/core/simulation.py
- src/pm6/state/storage.py
