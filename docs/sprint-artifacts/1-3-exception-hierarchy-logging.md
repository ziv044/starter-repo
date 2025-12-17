# Story 1.3: Exception Hierarchy & Logging

Status: done

## Story

As a **developer**,
I want **clear exceptions and structured logging**,
so that **I can debug issues and handle errors gracefully**.

## Acceptance Criteria

### AC1: PM6Error Base Class
**Given** pm6 encounters an error
**When** the error is raised
**Then** it inherits from `PM6Error` base class
**And** specific errors use appropriate subclasses (`AgentNotFoundError`, `CostLimitError`)

### AC2: Structured Logging
**Given** pm6 is running
**When** operations occur
**Then** logs are written via `logging.getLogger("pm6")`
**And** submodules use child loggers (`pm6.agents`, `pm6.cost`)
**And** log levels follow DEBUG/INFO/WARNING/ERROR conventions

## Tasks / Subtasks

- [x] Task 1: Create PM6Error exception hierarchy (AC: 1)
  - [x] PM6Error base class
  - [x] AgentNotFoundError
  - [x] CostLimitError
  - [x] SignatureMatchError
  - [x] SessionNotFoundError
  - [x] ConfigurationError
  - [x] StorageError
  - [x] SimulationError
  - [x] RuleViolationError

- [x] Task 2: Create logging infrastructure (AC: 2)
  - [x] configureLogging() function
  - [x] getLogger() with pm6. prefix
  - [x] LogLevel enum
  - [x] PM6LogFormatter with colors
  - [x] setDebugMode() for easy debugging
  - [x] LogContext context manager

## Dev Notes

### Exception Hierarchy

```python
PM6Error (base)
├── AgentNotFoundError
├── CostLimitError
├── SignatureMatchError
├── SessionNotFoundError
├── ConfigurationError
├── StorageError
├── SimulationError
└── RuleViolationError
```

### Logger Hierarchy

```
pm6 (root)
├── pm6.core
├── pm6.agents
├── pm6.state
├── pm6.cost
├── pm6.llm
└── pm6.testing
```

### References

- [Source: docs/architecture.md#AR11] - PM6Error hierarchy
- [Source: docs/prd.md#NFR15] - Clear error states

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- **Brownfield project**: Exception hierarchy and logging already implemented
- **All acceptance criteria verified**:
  - AC1: All exceptions inherit from PM6Error
  - AC2: Loggers use pm6.* namespace with child loggers

### File List

_Files verified (already existed):_
- src/pm6/exceptions.py (full hierarchy with 8 exception types)
- src/pm6/logging/__init__.py
- src/pm6/logging/config.py (configureLogging, getLogger, LogLevel)
- src/pm6/logging/tracer.py (InteractionTracer)
