# Story 1.1: Project Setup & Package Structure

Status: done

## Story

As a **developer**,
I want **to install pm6 via pip and have a properly structured Python package**,
so that **I can begin building simulations with a solid foundation**.

## Acceptance Criteria

### AC1: Editable Package Installation
**Given** a developer has cloned the pm6 repository
**When** they run `pip install -e .`
**Then** pm6 is installed as an editable package
**And** `from pm6 import Simulation` works without error

### AC2: Project Structure Compliance
**Given** the project structure exists
**When** examining the src/pm6/ directory
**Then** it follows the src/ layout with `__init__.py` exposing public API
**And** pyproject.toml defines package metadata and dependencies
**And** module files use camelCase naming (e.g., `agentConfig.py`)

### AC3: Version Accessibility
**Given** the package is installed
**When** running `python -c "import pm6; print(pm6.__version__)"`
**Then** the version string is displayed

## Tasks / Subtasks

- [ ] Task 1: Create pyproject.toml (AC: 1, 2)
  - [ ] Define package metadata (name, version, description, author)
  - [ ] Specify Python 3.10+ requirement
  - [ ] Add core dependencies (pydantic, pydantic-settings, anthropic, xxhash)
  - [ ] Add dev dependencies (pytest, pytest-asyncio, pytest-cov, ruff, mypy)
  - [ ] Configure ruff linting rules
  - [ ] Configure pytest settings

- [ ] Task 2: Create src/pm6/ directory structure (AC: 2)
  - [ ] Create src/pm6/__init__.py with version and public exports
  - [ ] Create src/pm6/core/__init__.py
  - [ ] Create src/pm6/agents/__init__.py
  - [ ] Create src/pm6/state/__init__.py
  - [ ] Create src/pm6/cost/__init__.py
  - [ ] Create src/pm6/llm/__init__.py
  - [ ] Create src/pm6/config/__init__.py
  - [ ] Create src/pm6/exceptions.py (PM6Error hierarchy)

- [ ] Task 3: Create supporting files (AC: 1, 2)
  - [ ] Create .env.example with required environment variables
  - [ ] Create .gitignore (Python, IDE, .env, db/, logs/)
  - [ ] Create README.md with quick start instructions
  - [ ] Create db/.gitkeep for default storage directory

- [ ] Task 4: Verify installation (AC: 1, 3)
  - [ ] Run `pip install -e .` and verify success
  - [ ] Verify `from pm6 import Simulation` placeholder works
  - [ ] Verify `pm6.__version__` returns version string
  - [ ] Run `ruff check src/` with no errors

## Dev Notes

### Architecture Compliance (CRITICAL)

**Source:** [docs/architecture.md#Implementation-Patterns-Consistency-Rules]

#### Naming Conventions (MANDATORY)
- **Functions/methods:** `camelCase` - `getAgent()`, `computeSignature()`
- **Variables:** `camelCase` - `agentName`, `currentState`
- **Classes:** `PascalCase` - `AgentConfig`, `Simulation`
- **Constants:** `UPPER_SNAKE_CASE` - `DEFAULT_MODEL`, `MAX_RETRIES`
- **Private members:** `_leadingUnderscore` - `_computeHash()`
- **Module files:** `camelCase.py` - `agentConfig.py`, `costTracker.py`
- **JSON keys:** `camelCase` - `{"agentName": "pm", "situationType": "crisis"}`

#### Exception Hierarchy Pattern
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

#### Docstring Pattern (Google Style)
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

### Project Structure (EXACT)

**Source:** [docs/architecture.md#Project-Structure-Boundaries]

```
pm6/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   └── pm6/
│       ├── __init__.py           # Package exports + version
│       ├── exceptions.py         # PM6Error hierarchy
│       ├── core/
│       │   └── __init__.py
│       ├── agents/
│       │   └── __init__.py
│       ├── state/
│       │   └── __init__.py
│       ├── cost/
│       │   └── __init__.py
│       ├── llm/
│       │   └── __init__.py
│       └── config/
│           └── __init__.py
├── tests/
│   └── conftest.py               # Shared fixtures
└── db/
    └── .gitkeep
```

### Dependencies

**Source:** [docs/architecture.md#Starter-Template-Evaluation]

#### Core Dependencies
| Package | Purpose | Notes |
|---------|---------|-------|
| pydantic | Data validation, models | Used for AgentConfig, Response |
| pydantic-settings | Environment config | .env loading |
| anthropic | Claude API | Primary LLM integration |
| xxhash | Fast hashing | Signature computation |

#### Dev Dependencies
| Package | Purpose | Notes |
|---------|---------|-------|
| pytest | Testing framework | Main test runner |
| pytest-asyncio | Async test support | For async LLM operations |
| pytest-cov | Coverage reporting | Track test coverage |
| ruff | Linting + formatting | Replaces black + flake8 |
| mypy | Type checking | Validate type hints |

### pyproject.toml Template

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pm6"
version = "0.1.0"
description = "LLM-powered simulation engine"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "anthropic>=0.20",
    "xxhash>=3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
```

### src/pm6/__init__.py Template

```python
"""pm6 - LLM-powered simulation engine.

This module provides infrastructure for cost-effective, smart LLM-powered simulations.
"""

__version__ = "0.1.0"

# Public API exports (placeholder for Story 1.5)
# from pm6.core.simulation import Simulation
# from pm6.agents.agentConfig import AgentConfig
# from pm6.agents.memoryPolicy import MemoryPolicy

# Placeholder until Simulation class is implemented
class Simulation:
    """Placeholder Simulation class for package verification."""
    pass

__all__ = ["Simulation", "__version__"]
```

### src/pm6/exceptions.py Template

```python
"""pm6 exception hierarchy.

All pm6 exceptions inherit from PM6Error for easy catching.
"""


class PM6Error(Exception):
    """Base exception for all pm6 errors."""
    pass


class AgentNotFoundError(PM6Error):
    """Raised when requested agent doesn't exist in simulation."""
    pass


class CostLimitError(PM6Error):
    """Raised when operation would exceed cost limits."""
    pass


class SignatureMatchError(PM6Error):
    """Raised when signature lookup fails."""
    pass


class StateError(PM6Error):
    """Raised when state operations fail."""
    pass


class ConfigurationError(PM6Error):
    """Raised when configuration is invalid."""
    pass
```

### .env.example Template

```bash
# pm6 Configuration
# Copy this to .env and fill in your values

# Anthropic API (required)
ANTHROPIC_API_KEY=your_api_key_here

# Storage path (optional, defaults to ./db)
PM6_DB_PATH=./db

# Default model (optional)
PM6_DEFAULT_MODEL=claude-sonnet-4-20250514

# Cost limit per session (optional)
PM6_COST_LIMIT=1.00
```

### .gitignore Template

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local

# pm6 specific
db/
!db/.gitkeep
logs/
*.log

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/

# OS
.DS_Store
Thumbs.db
```

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming): FULL COMPLIANCE
- Detected conflicts or variances: NONE
- All module subdirectories start empty with only `__init__.py`
- Actual module files (agentConfig.py, etc.) will be created in subsequent stories

### References

- [Source: docs/architecture.md#Starter-Template-Evaluation] - Project setup approach
- [Source: docs/architecture.md#Implementation-Patterns-Consistency-Rules] - Naming conventions
- [Source: docs/architecture.md#Project-Structure-Boundaries] - Directory structure
- [Source: docs/prd.md#Developer-Tool-Requirements] - Installation method
- [Source: docs/epics.md#Story-1.1] - User story and acceptance criteria

## Dev Agent Record

### Context Reference

Story context created by create-story workflow from:
- docs/epics.md (Story 1.1 definition)
- docs/architecture.md (technical requirements)
- docs/prd.md (project requirements)

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Initial story, no previous debug logs

### Completion Notes List

- **Brownfield project**: All files already existed from prior development
- **All acceptance criteria verified**:
  - AC1: `pip install -e .` successful, `from pm6 import Simulation` works
  - AC2: src/pm6/ structure exists with camelCase naming conventions
  - AC3: `pm6.__version__` returns "0.1.0"
- **Ruff configuration updated**: Added N815, N999 to ignore list for camelCase naming
- **Minor style fixes**: Fixed import sorting in `__main__.py`

### File List

_Files verified (already existed):_
- pyproject.toml (updated ruff ignore rules)
- .env.example
- .gitignore
- README.md
- src/pm6/__init__.py (comprehensive with lazy imports)
- src/pm6/exceptions.py (full hierarchy)
- src/pm6/core/__init__.py + many modules
- src/pm6/agents/__init__.py + many modules
- src/pm6/state/__init__.py + many modules
- src/pm6/cost/__init__.py + many modules
- src/pm6/llm/__init__.py + many modules
- src/pm6/config/__init__.py + settings.py
- tests/conftest.py + 15+ test files
- db/ directory

_Files modified:_
- pyproject.toml (added N815, N999 to ruff ignore)
- src/pm6/__main__.py (fixed import sorting, line length, f-string)
