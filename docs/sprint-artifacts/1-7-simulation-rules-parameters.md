# Story 1.7: Simulation Rules & Parameters

Status: done

## Story

As a **developer**,
I want **to configure simulation rules, constraints, and parameters**,
so that **simulations behave according to my specifications**.

## Acceptance Criteria

- [x] AC1: sim.configure(mode="crisis") stores parameters
- [x] AC2: sim.setWorldState({...}) stores world state
- [x] AC3: sim.getWorldState() returns current state
- [x] AC4: Rules and constraints are enforced

## Completion Notes

- **Brownfield**: Rules system fully implemented
- SimulationRules class with RuleType enum
- Rule evaluation with violations tracking
- World state get/set methods work

## Files

- src/pm6/core/rules.py
- src/pm6/core/simulation.py (setWorldState, getWorldState)
