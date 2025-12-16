---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - docs/prd.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2025-12-16'
project_name: 'pm6'
user_name: 'Ziv04'
date: '2025-12-15'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
47 FRs organized into 8 capability areas covering the full simulation engine lifecycle: creation, agent management, state persistence, cost optimization, session management, developer API, configuration, and testing infrastructure. The core pattern is an LLM orchestration layer that makes simulation-grade AI interactions cost-effective and sustainable.

**Non-Functional Requirements:**
18 NFRs focused on:
- Performance metrics & visibility (NFR1-5): Track everything, optimize continuously
- Integration (NFR6-10): Anthropic ecosystem (Claude, Skills, caching), configurable DB backends
- Reliability (NFR11-15): No data loss, graceful recovery, transactional state
- Security (NFR16-18): Credential management, access control, cost limits

**Scale & Complexity:**
- Primary domain: Python backend infrastructure / SDK
- Complexity level: Medium-High
- Estimated architectural components: 6-8 major modules

### Technical Constraints & Dependencies

- Python 3.x (primary language, standard package management)
- Anthropic API (Claude models - mandatory)
- Prompt caching (Anthropic feature - key to cost optimization)
- Claude Skills (tool use for DB/file operations)
- Database backend (configurable - SQLite for dev, production TBD)
- No external services beyond Anthropic API

### Cross-Cutting Concerns Identified

1. **Cost Tracking** - Every LLM interaction must be metered, logged, and attributed
2. **Mode Management** - Test mode vs production affects all agent behavior
3. **State Persistence** - Sessions, agent memory, world state all need coordinated storage
4. **Token Management** - Context limits affect compaction, caching, and response strategies
5. **Agent Identification** - Determining relevant agents affects cost and response quality

## Starter Template Evaluation

### Primary Technology Domain

Python backend infrastructure library - LLM orchestration SDK for simulation engines. This is custom tooling, not a web/mobile application.

### Starter Options Considered

| Option | Pros | Cons |
|--------|------|------|
| Manual Setup | Full control, minimal cruft | Requires knowing patterns |
| cookiecutter-pypackage | Complete Python package template | Overkill for single-purpose lib |
| poetry new | Quick init with poetry | Less flexible than manual |

### Selected Approach: Manual Setup with Modern Python Standards

**Rationale:**
- Infrastructure library requires custom structure for simulation modules
- No need for publishing boilerplate (PyPI, docs site) in MVP
- Modern pyproject.toml (PEP 517/518) provides all needed configuration
- src/ layout prevents import confusion during development

**Initialization Commands:**
```bash
mkdir -p src/pm6 tests
touch src/pm6/__init__.py pyproject.toml .env.example
```

### Architectural Decisions for Project Structure

**Language & Runtime:**
- Python 3.10+ (for modern typing features)
- Type hints throughout (mypy compatible)

**Package Configuration:**
- pyproject.toml (PEP 517/518)
- src/ layout for clean imports

**Build Tooling:**
- pip for installation
- ruff for linting + formatting (replaces black + flake8)

**Testing Framework:**
- pytest with pytest-asyncio
- pytest-cov for coverage

**Code Organization:**
```
src/pm6/
├── __init__.py       # Package exports
├── core/             # Core simulation engine
├── agents/           # Agent system
├── state/            # State management
├── cost/             # Cost optimization layer
└── api/              # Developer API
```

**Development Experience:**
- .env configuration via pydantic-settings
- Type checking with mypy
- Pre-commit hooks optional

## Core Architectural Decisions

### Data Architecture

**Storage Strategy:**
- Folder-based storage (`./db/`) for development speed
- Structure: `db/{simulation_name}/{agents|sessions|responses}/`
- Format: JSON files for human readability, indexed by signature

**Hashing:**
- xxHash for all signature computation (speed over crypto)
- Signatures combine: agent_name + situation_type + state_bucket + input_intent

**Response Caching:**
- Pre-generated responses stored by structural signature
- Multiple responses collected per signature for variety
- Random selection from cached options when serving

**State Bucketing:**
- Continuous values bucketed into ranges (approval: 60-70 → "medium")
- Enables response sharing across similar-but-not-identical situations

### Cost Optimization Architecture

**DB-First Lookup Flow:**
1. Compute structural signature for incoming interaction
2. Check DB for matching signatures
3. If match: return pre-generated response (random from options)
4. If no match: call LLM, store response with signature

**Prompt Caching (Anthropic):**
- cache_control on system prompts (shared across all calls)
- cache_control on agent definitions (shared per agent)
- Expected savings: 90% token reduction on repeated contexts

**Model Routing:**

| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Context compaction | Haiku | Routine summarization |
| History summarization | Haiku | Non-critical |
| Agent responses | Sonnet | Core interaction quality |
| Complex reasoning | Opus | When needed (configurable) |

### Agent Architecture

**Configuration Pattern:**
- Pydantic models for all agent configuration
- Validation and serialization built-in
- Integrates with pydantic-settings

**Memory Policies:**
- FULL: Retain complete history
- SUMMARY: Compact after N turns (default)
- SELECTIVE: Category-based retention
- NONE: Stateless agent

**Agent Identification:**
- Explicit routing via situation_type tags
- Agents declare which situations they handle
- Multiple agents can respond to same situation (orchestration)

### Developer API

**Design Principles:**
- Async-first for all LLM operations
- Context manager for lifecycle management
- Built-in cost/stats visibility
- Simple save/load for checkpoints

**Core API Surface:**
- `Simulation.create()` - Initialize new simulation
- `Simulation.load()` - Resume from checkpoint
- `sim.interact()` - Send user input, get agent response
- `sim.get_stats()` - Cost and performance metrics
- `sim.save()` - Create checkpoint

### Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Folder-based DB | Dev speed, human-readable |
| Hash | xxHash | Speed for non-crypto use |
| Matching | Structural signatures | Balance: not too strict, not too complex |
| Caching | Multi-response collection | Variety + reuse |
| Config | Pydantic models | Validation + settings integration |
| API | Async + context manager | Pythonic, explicit lifecycle |
| Models | Haiku/Sonnet routing | Cost optimization |

## Implementation Patterns & Consistency Rules

### Naming Conventions

**Python Code (camelCase preference):**
- Functions/methods: `camelCase` - `getAgent()`, `computeSignature()`
- Variables: `camelCase` - `agentName`, `currentState`
- Classes: `PascalCase` - `AgentConfig`, `Simulation`
- Constants: `UPPER_SNAKE_CASE` - `DEFAULT_MODEL`, `MAX_RETRIES`
- Private members: `_leadingUnderscore` - `_computeHash()`
- Module files: `camelCase.py` - `agentConfig.py`, `costTracker.py`

**JSON/Data Fields:**
- All keys: `camelCase`
- Example: `{"agentName": "pm", "situationType": "crisis"}`

### File Organization

**Module Structure:**
```
src/pm6/
├── __init__.py
├── agents/
│   ├── __init__.py
│   ├── agentConfig.py
│   ├── memoryPolicy.py
│   └── routing.py
├── cost/
│   ├── __init__.py
│   ├── signatureCompute.py
│   └── modelRouter.py
├── state/
│   ├── __init__.py
│   ├── storage.py
│   └── checkpoints.py
└── core/
    ├── __init__.py
    └── simulation.py
```

**Test Organization:**
- Tests mirror src structure in `tests/`
- Fixtures in `tests/fixtures/`
- Shared fixtures in `tests/conftest.py`

### Error Handling Pattern

**Exception Hierarchy:**
```python
class PM6Error(Exception):
    """Base pm6 exception"""

class AgentNotFoundError(PM6Error):
    """Agent doesn't exist"""

class CostLimitError(PM6Error):
    """Cost limit exceeded"""

class SignatureMatchError(PM6Error):
    """Signature lookup failed"""
```

### Logging Pattern

**Logger Setup:**
- Single logger: `logging.getLogger("pm6")`
- Submodule loggers: `logging.getLogger("pm6.agents")`

**Log Levels:**
- DEBUG: Internal details (signatures, hashes)
- INFO: Normal operations (cache hits, saves)
- WARNING: Fallbacks, degraded operation
- ERROR: Failures requiring attention

### Docstring Pattern (Google Style)

```python
def getAgentResponse(self, agentName: str, userInput: str) -> Response:
    """Send user input to an agent and get response.

    Args:
        agentName: Name of the agent to interact with.
        userInput: User's input text.

    Returns:
        Response object containing agent's reply and metadata.

    Raises:
        AgentNotFoundError: If agent doesn't exist in simulation.
        CostLimitError: If cost limit would be exceeded.
    """
```

### Type Hints

**Required on all public API:**
```python
def interact(self, agent: str, userInput: str) -> Response:
async def save(self, name: str) -> Path:
def getStats(self) -> Stats:
```

### Enforcement

**All AI Agents MUST:**
- Use camelCase for functions, variables, file names
- Use PascalCase for classes only
- Use type hints on all public functions
- Include Google-style docstrings on public API
- Use the PM6Error hierarchy for exceptions
- Use camelCase for all JSON keys

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
│       └── ci.yml
├── src/
│   └── pm6/
│       ├── __init__.py                 # Package exports
│       ├── exceptions.py               # PM6Error hierarchy
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── simulation.py           # Simulation class (main entry)
│       │   ├── response.py             # Response model
│       │   └── stats.py                # Stats tracking
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── agentConfig.py          # AgentConfig Pydantic model
│       │   ├── memoryPolicy.py         # Memory policy enum + logic
│       │   ├── routing.py              # Agent identification/routing
│       │   └── generator.py            # Natural language → agent
│       │
│       ├── state/
│       │   ├── __init__.py
│       │   ├── storage.py              # Folder-based DB operations
│       │   ├── checkpoints.py          # Save/load functionality
│       │   ├── compaction.py           # Context summarization
│       │   └── tokenBudget.py          # Token management
│       │
│       ├── cost/
│       │   ├── __init__.py
│       │   ├── signatureCompute.py     # xxHash signature generation
│       │   ├── stateBucketing.py       # State value bucketing
│       │   ├── responseCache.py        # Multi-response storage
│       │   ├── modelRouter.py          # Haiku/Sonnet routing
│       │   ├── promptCache.py          # Anthropic cache_control
│       │   └── costTracker.py          # Usage metrics
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── anthropicClient.py      # Anthropic API wrapper
│       │   └── tools.py                # Claude Skills integration
│       │
│       └── config/
│           ├── __init__.py
│           └── settings.py             # pydantic-settings config
│
├── tests/
│   ├── conftest.py                     # Shared fixtures
│   ├── test_core/
│   │   ├── test_simulation.py
│   │   └── test_stats.py
│   ├── test_agents/
│   │   ├── test_agentConfig.py
│   │   ├── test_memoryPolicy.py
│   │   └── test_routing.py
│   ├── test_state/
│   │   ├── test_storage.py
│   │   ├── test_checkpoints.py
│   │   └── test_compaction.py
│   ├── test_cost/
│   │   ├── test_signatureCompute.py
│   │   ├── test_responseCache.py
│   │   └── test_modelRouter.py
│   └── fixtures/
│       ├── sampleAgents.json
│       └── sampleResponses.json
│
├── db/                                  # Default storage (gitignored)
│   └── .gitkeep
│
└── docs/                               # Project documentation
    ├── prd.md
    └── architecture.md
```

### Requirements to Structure Mapping

| PRD Category | Module | Files |
|--------------|--------|-------|
| FR1-4 (Simulation Creation) | `core/` | `simulation.py`, `response.py` |
| FR5-11 (Agent System) | `agents/` | `agentConfig.py`, `memoryPolicy.py`, `routing.py`, `generator.py` |
| FR12-18 (State Management) | `state/` | `storage.py`, `checkpoints.py`, `compaction.py`, `tokenBudget.py` |
| FR19-24 (Cost Optimization) | `cost/` | `signatureCompute.py`, `responseCache.py`, `modelRouter.py`, `costTracker.py` |
| FR25-29 (Session Management) | `state/` + `core/` | `checkpoints.py`, `simulation.py` |
| FR30-35 (Developer API) | `core/` | `simulation.py` (public API surface) |
| FR36-39 (Configuration) | `config/` | `settings.py` |
| FR40-47 (Testing) | `tests/` | All test files |

### Module Boundaries

**User code imports from:**
```python
from pm6 import Simulation, AgentConfig, MemoryPolicy
from pm6.exceptions import PM6Error, AgentNotFoundError
```

**Internal dependencies:**
- `core/` → depends on `agents/`, `state/`, `cost/`, `llm/`
- `agents/` → depends on `config/`
- `state/` → depends on `config/`
- `cost/` → depends on `state/`, `config/`
- `llm/` → depends on `config/`
- `config/` → no internal dependencies
- `exceptions.py` → no internal dependencies

### Data Flow

```
User Input
    │
    ▼
Simulation.interact()
    │
    ├──► Agent Routing (which agent?)
    │
    ├──► Signature Compute (xxHash)
    │
    ├──► Response Cache Check (DB-first)
    │       │
    │       ├── HIT ──► Return cached response
    │       │
    │       └── MISS ──► Continue to LLM
    │
    ├──► Prompt Cache (Anthropic cache_control)
    │
    ├──► Model Router (Haiku/Sonnet/Opus)
    │
    └──► Anthropic API Call
            │
            ▼
        Store Response + Return
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** All technology choices (Python 3.10+, Pydantic, Anthropic SDK, xxHash) work together without conflicts. Async-first design aligns with SDK patterns.

**Pattern Consistency:** camelCase naming applied consistently across code, files, and JSON. Implementation patterns support all architectural decisions.

**Structure Alignment:** src/ layout with modular boundaries supports clean dependency flow and testability.

### Requirements Coverage ✅

**Functional Requirements:** All 47 FRs mapped to specific modules:
- FR1-4 → `core/`
- FR5-11 → `agents/`
- FR12-18 → `state/`
- FR19-24 → `cost/`
- FR25-29 → `state/` + `core/`
- FR30-35 → `core/` (API surface)
- FR36-39 → `config/`
- FR40-47 → `tests/`

**Non-Functional Requirements:** All 18 NFRs addressed:
- NFR1-5 (Performance) → `cost/costTracker.py`, `core/stats.py`
- NFR6-10 (Integration) → `llm/anthropicClient.py`, `cost/promptCache.py`
- NFR11-15 (Reliability) → Exception hierarchy, state persistence
- NFR16-18 (Security) → pydantic-settings (env-based), cost limits

### Implementation Readiness ✅

**Decision Completeness:** All critical decisions documented with rationale
**Structure Completeness:** Full directory tree with 30+ specific files
**Pattern Completeness:** Naming, error handling, logging, docstrings defined

### Gap Analysis

**Critical Gaps:** None identified
**Important Gaps:** None identified
**Minor Suggestions:** Type stubs, API docs (post-MVP)

### Architecture Readiness Assessment

**Overall Status:** ✅ READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Simple, focused scope (6 modules)
- Clear separation of concerns
- Cost optimization as first-class architectural concern
- Comprehensive testing structure

**First Implementation Priority:**
1. Project setup (pyproject.toml, directory structure)
2. `config/` + `exceptions.py` (no dependencies)
3. `agents/agentConfig.py` + `memoryPolicy.py`
4. `cost/signatureCompute.py` + `responseCache.py`
5. `state/storage.py` + `checkpoints.py`
6. `llm/anthropicClient.py`
7. `core/simulation.py` (ties everything together)

## Architecture Completion Summary

**Architecture Workflow:** COMPLETED
**Date:** 2025-12-16
**Document:** [docs/architecture.md](docs/architecture.md)

### Deliverables

- 7 core architectural decisions documented
- 6 implementation patterns defined (naming, errors, logging, docstrings, types, enforcement)
- 6 modules specified with clear boundaries
- 47 FRs + 18 NFRs fully supported

### Next Steps

1. Create Epics & Stories (`/bmad:bmm:workflows:create-epics-stories`)
2. Run Implementation Readiness Check
3. Sprint Planning
4. Begin implementation

---

**Architecture Status:** READY FOR IMPLEMENTATION
