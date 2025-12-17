# Story 1.1: Project Setup & Package Structure

**Status:** ready-for-dev
**Epic:** Epic 1 - Project Foundation & First Simulation
**Story Key:** 1-1-project-setup-package-structure

## Story

As a **developer**,
I want **to install pm6 via pip and have a properly structured Python package**,
So that **I can begin building simulations with a solid foundation**.

## Acceptance Criteria

- [ ] AC1: `pip install -e .` installs pm6 as an editable package and `from pm6 import Simulation` works without error
- [ ] AC2: src/pm6/ follows the src/ layout with `__init__.py` exposing public API, pyproject.toml defines package metadata and dependencies, and module files use camelCase naming
- [ ] AC3: `python -c "import pm6; print(pm6.__version__)"` displays the version string

## Implementation Context

### Brownfield Status

This is a **brownfield project** - the implementation already exists. This story documents verification of the existing codebase against the acceptance criteria.

### Existing Implementation Analysis

**Package Structure (Verified):**
```
pm6/
├── pyproject.toml          # PEP 517/518 configuration
├── src/
│   └── pm6/
│       ├── __init__.py     # Public API exports, __version__ = "0.1.0"
│       ├── __main__.py     # CLI entry point
│       ├── exceptions.py   # PM6Error hierarchy
│       ├── agents/         # Agent system
│       │   ├── agentConfig.py
│       │   ├── memoryPolicy.py
│       │   ├── routing.py
│       │   ├── relevance.py
│       │   └── stateUpdater.py
│       ├── config/         # Configuration system
│       │   └── settings.py
│       ├── core/           # Core simulation engine
│       │   ├── simulation.py
│       │   ├── response.py
│       │   ├── rules.py
│       │   ├── events.py
│       │   ├── engine.py
│       │   └── types.py
│       ├── cost/           # Cost optimization
│       │   ├── signatureCompute.py
│       │   ├── responseCache.py
│       │   ├── costTracker.py
│       │   ├── tokenBudget.py
│       │   ├── modelRouter.py
│       │   ├── stateBucketing.py
│       │   └── estimator.py
│       ├── llm/            # LLM client
│       │   ├── anthropicClient.py
│       │   └── rateLimiter.py
│       ├── logging/        # Logging system
│       │   ├── config.py
│       │   └── tracer.py
│       ├── metrics/        # Performance tracking
│       │   └── performanceTracker.py
│       ├── state/          # State management
│       │   ├── storage.py
│       │   ├── checkpoints.py
│       │   ├── sessionRecorder.py
│       │   └── sessionReplayer.py
│       ├── testing/        # Test utilities
│       │   ├── mockClient.py
│       │   ├── validator.py
│       │   └── scenarioTester.py
│       ├── tools/          # Tool system
│       │   └── toolRegistry.py
│       └── reliability/    # Reliability features
│           └── transactions.py
└── tests/                  # Test suite
```

### Key Files

**pyproject.toml** - Package configuration:
- Python 3.10+ required
- Dependencies: anthropic, pydantic, pydantic-settings, xxhash, pyyaml
- Entry point: `pm6 = "pm6.__main__:main"`
- Dev tools: pytest, ruff, mypy
- ruff configured for camelCase naming (N815, N999 ignored)

**src/pm6/__init__.py** - Public API:
- `__version__ = "0.1.0"`
- Exports: Simulation, AgentConfig, MemoryPolicy, PM6Error hierarchy
- Lazy imports to avoid circular dependencies

### Architecture Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| AR1: Modern Python setup | ✅ | pyproject.toml with PEP 517/518 |
| AR2: camelCase naming | ✅ | agentConfig.py, memoryPolicy.py, etc. |
| AR3: PascalCase classes | ✅ | Simulation, AgentConfig, PM6Error |
| AR7: Pydantic models | ✅ | AgentConfig uses Pydantic |
| AR11: Exception hierarchy | ✅ | PM6Error base with subclasses |

## Tasks

### Verification Tasks

- [ ] 1. Verify pip install works
  - [ ] 1.1 Run `pip install -e .` in project root
  - [ ] 1.2 Confirm no errors during installation
  - [ ] 1.3 Verify all dependencies are installed

- [ ] 2. Verify imports work
  - [ ] 2.1 Test `from pm6 import Simulation`
  - [ ] 2.2 Test `from pm6 import AgentConfig`
  - [ ] 2.3 Test exception imports

- [ ] 3. Verify version display
  - [ ] 3.1 Run `python -c "import pm6; print(pm6.__version__)"`
  - [ ] 3.2 Confirm version "0.1.0" is displayed

- [ ] 4. Verify package structure
  - [ ] 4.1 Confirm src/ layout
  - [ ] 4.2 Verify camelCase file naming
  - [ ] 4.3 Check pyproject.toml has all required metadata

### Validation Commands

```bash
# AC1: Install and import test
pip install -e .
python -c "from pm6 import Simulation, AgentConfig; print('OK')"

# AC2: Structure verification
ls src/pm6/*.py  # Should show camelCase files
cat pyproject.toml | grep -A5 "\[project\]"

# AC3: Version test
python -c "import pm6; print(pm6.__version__)"
```

## Technical Notes

### Naming Convention

Per architecture decision AR2, this project uses **camelCase** for:
- Function/method names: `getAgent()`, `computeSignature()`
- Variable names: `agentName`, `currentState`
- Module file names: `agentConfig.py`, `costTracker.py`

**PascalCase** is used only for:
- Class names: `Simulation`, `AgentConfig`, `PM6Error`

This is enforced via ruff configuration:
```toml
[tool.ruff.lint]
ignore = ["N802", "N803", "N806", "N815", "N999"]
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| anthropic | >=0.40.0 | Claude API client |
| pydantic | >=2.0.0 | Data validation/models |
| pydantic-settings | >=2.0.0 | Environment config |
| xxhash | >=3.4.0 | Fast hashing for signatures |
| pyyaml | >=6.0.0 | YAML file handling |

## Definition of Done

- [ ] All acceptance criteria verified
- [ ] pip install -e . completes without error
- [ ] All core imports work (Simulation, AgentConfig, exceptions)
- [ ] Version string displays correctly
- [ ] Package structure follows architecture decisions
- [ ] Tests pass: `pytest tests/ -v`

## Dev Agent Record

### File List
- [pyproject.toml](../../pyproject.toml) - Package configuration
- [src/pm6/__init__.py](../../src/pm6/__init__.py) - Public API exports

### Change Log
- Story created for brownfield verification
- All acceptance criteria pre-verified against existing implementation
