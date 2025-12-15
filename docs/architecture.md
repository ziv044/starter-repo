---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - docs/prd.md
  - docs/research-cicd.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2025-12-15'
project_name: 'pm6'
user_name: 'Ziv04'
date: '2025-12-15'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
26 FRs organized into 6 capability areas covering logging, replay, agent configuration, environment configuration, testing infrastructure, and CI/CD. The core architectural pattern is a record-replay system for deterministic LLM testing.

**Non-Functional Requirements:**
12 NFRs focused on code quality (PEP 8, black, ruff), testability (deterministic, <30s), integration compatibility (Anthropic SDK, pytest 8.x), and security (env-only secrets).

**Scale & Complexity:**
- Primary domain: Python backend infrastructure
- Complexity level: Low
- Estimated architectural components: 4-5 modules

### Technical Constraints & Dependencies

- Python 3.12+
- Anthropic SDK (latest stable)
- pytest 8.x with pytest-asyncio
- GitHub Actions (ubuntu-latest runner)
- No external databases or services

### Cross-Cutting Concerns Identified

1. **Mode Management** - LIVE/REPLAY/HYBRID state affects all LLM operations
2. **Configuration Hierarchy** - Global defaults with per-agent overrides
3. **Session Management** - Log file naming, auto-increment, lifecycle

## Starter Template Evaluation

### Primary Technology Domain

Python backend infrastructure library - custom tooling for LLM testing with record-replay pattern.

### Starter Options Considered

No traditional starter template applicable. This is a Python library/infrastructure project requiring manual project setup following modern Python conventions.

### Selected Approach: Manual Setup with Modern Python Standards

**Rationale:**
- Infrastructure library, not a web application
- Requires specific structure for LLMLogger, LLMReplayProvider modules
- Modern pyproject.toml-based packaging

**Initialization Commands:**
```bash
mkdir -p src/pm6 tests .github/workflows
touch src/pm6/__init__.py pyproject.toml .env.example
```

### Architectural Decisions for Project Structure

**Language & Runtime:**
- Python 3.12+
- Type hints throughout (mypy compatible)

**Package Configuration:**
- pyproject.toml (PEP 517/518)
- src/ layout for import safety

**Build Tooling:**
- pip for installation
- black + ruff for formatting/linting

**Testing Framework:**
- pytest 8.x with pytest-asyncio
- pytest-cov for coverage

**Code Organization:**
```
src/pm6/
├── __init__.py      # Package exports
├── logger.py        # LLMLogger class
├── replay.py        # LLMReplayProvider class
├── config.py        # Settings, AgentConfig
└── modes.py         # Mode enum (LIVE/REPLAY/HYBRID)
```

**Development Experience:**
- .env configuration via pydantic-settings
- GitHub Actions CI on push/PR

## Core Architectural Decisions

### Data Architecture

**JSONL Storage Location:**
- Decision: Configurable via `LOG_DIR` setting with default `./logs/`
- Rationale: Flexibility for different environments (dev vs CI)

**Session Naming Convention:**
- Decision: Named + auto-increment (`{name}_{001}.jsonl`)
- Rationale: Human-readable, prevents overwrites, supports multiple test sessions

### Mode Management

**Mode Switching Pattern:**
- Decision: Global mode only (LIVE/REPLAY/HYBRID)
- Rationale: Simpler implementation, sufficient for testing needs
- Implementation: Single `Settings.mode` controls all LLM calls

### Replay System

**Replay Matching Strategy:**
- Decision: Sequential by agent name
- Rationale: Deterministic, simple, aligns with test execution order

**Missing Replay Data Behavior:**
- Decision: Configurable strict mode
- Options: `strict=True` raises exception, `strict=False` falls back to LIVE
- Default: `strict=True` (fail fast in tests)

### Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Log storage | Configurable `LOG_DIR` | Environment flexibility |
| Session naming | Named + increment | Human-readable, no conflicts |
| Mode pattern | Global only | Simplicity |
| Replay matching | Sequential by agent | Deterministic |
| Missing data | Configurable strict | Fail fast default |

## Implementation Patterns & Consistency Rules

### Naming Conventions

**Python Code (PEP 8):**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### JSONL Log Format

```json
{
  "timestamp": "2025-12-15T14:30:22.123Z",
  "agent_name": "story_agent",
  "request": {"model": "...", "messages": [...]},
  "response": {"content": "...", "usage": {...}},
  "duration_ms": 1234
}
```

### Module Exports Pattern

```python
# src/pm6/__init__.py
from .logger import LLMLogger
from .replay import LLMReplayProvider
from .config import Settings
from .modes import Mode

__all__ = ["LLMLogger", "LLMReplayProvider", "Settings", "Mode"]
```

### Error Handling Pattern

```python
# src/pm6/exceptions.py
class PM6Error(Exception): pass
class ReplayNotFoundError(PM6Error): pass
class SessionNotFoundError(PM6Error): pass
```

### Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── test_logger.py       # LLMLogger tests
├── test_replay.py       # LLMReplayProvider tests
├── test_config.py       # Settings tests
└── fixtures/            # Test JSONL files
    └── sample_session.jsonl
```

### Docstring Pattern (Google Style)

```python
def method(self, param: str) -> bool:
    """Short description.

    Args:
        param: Description of param.

    Returns:
        Description of return value.

    Raises:
        ReplayNotFoundError: When replay data missing.
    """
```

## Project Structure & Boundaries

### Complete Project Directory Structure

```
pm6/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── tests.yml
├── src/
│   └── pm6/
│       ├── __init__.py          # Package exports
│       ├── modes.py             # Mode enum (LIVE/REPLAY/HYBRID)
│       ├── config.py            # Settings class (pydantic-settings)
│       ├── logger.py            # LLMLogger class
│       ├── replay.py            # LLMReplayProvider class
│       └── exceptions.py        # Custom exceptions
├── tests/
│   ├── conftest.py              # Shared pytest fixtures
│   ├── test_modes.py
│   ├── test_config.py
│   ├── test_logger.py
│   ├── test_replay.py
│   └── fixtures/
│       └── sample_session.jsonl
└── logs/                        # Default log directory (gitignored)
```

### Requirements to Structure Mapping

| PRD Category | Module | Purpose |
|--------------|--------|---------|
| FR1-5 (Logging) | `logger.py` | LLMLogger class |
| FR6-12 (Replay) | `replay.py` | LLMReplayProvider class |
| FR13-15 (Agent Config) | `config.py` | Settings with mode |
| FR16-20 (Env Config) | `config.py` | pydantic-settings |
| FR21-26 (Testing/CI) | `tests/`, `.github/` | pytest + GitHub Actions |

### Module Boundaries

- **User code** imports from `pm6` package exports
- **logger.py** depends on `modes.py`, `config.py`
- **replay.py** depends on `modes.py`, `config.py`, `exceptions.py`
- **config.py** depends on `modes.py`
- **modes.py** and **exceptions.py** have no internal dependencies

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** All technology choices work together without conflicts. Python 3.12 + Anthropic SDK + pytest 8.x + pydantic-settings form a coherent, modern Python stack.

**Pattern Consistency:** Implementation patterns (PEP 8 naming, Google docstrings, JSONL format) align with Python ecosystem standards.

**Structure Alignment:** src/ layout supports clean imports; module boundaries are clear with minimal dependencies.

### Requirements Coverage ✅

**Functional Requirements:** All 26 FRs mapped to specific modules:
- FR1-5 → logger.py
- FR6-12 → replay.py
- FR13-20 → config.py
- FR21-26 → tests/, .github/

**Non-Functional Requirements:** All 12 NFRs addressed:
- Code quality via black + ruff
- Deterministic testing via replay system
- <30s test execution (unit tests only)
- Security via env-only secrets

### Implementation Readiness ✅

**Decision Completeness:** All critical decisions documented with rationale
**Structure Completeness:** Full directory tree specified
**Pattern Completeness:** Naming, error handling, JSONL format defined

### Gap Analysis

**Critical Gaps:** None identified
**Important Gaps:** None identified
**Minor Suggestions:** Type stubs could be added post-MVP

### Architecture Readiness Assessment

**Overall Status:** ✅ READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Simple, focused scope (4 modules)
- Clear separation of concerns
- Deterministic testing capability
- No external dependencies beyond Anthropic SDK

**First Implementation Priority:**
1. Project setup (pyproject.toml, directory structure)
2. modes.py + exceptions.py (no dependencies)
3. config.py (depends on modes)
4. logger.py (core functionality)
5. replay.py (depends on all above)
6. Tests + CI/CD

## Architecture Completion Summary

**Architecture Workflow:** COMPLETED ✅
**Date:** 2025-12-15
**Document:** [docs/architecture.md](docs/architecture.md)

### Deliverables

- 5 core architectural decisions documented
- 6 implementation patterns defined
- 5 modules specified with clear boundaries
- 26 FRs + 12 NFRs fully supported

### Next Steps

1. Create Epics & Stories (`/bmad:bmm:workflows:create-epics-stories`)
2. Run Implementation Readiness Check
3. Sprint Planning
4. Begin implementation

---

**Architecture Status:** ✅ READY FOR IMPLEMENTATION
