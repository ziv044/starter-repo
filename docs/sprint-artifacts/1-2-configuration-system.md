# Story 1.2: Configuration System

Status: done

## Story

As a **developer**,
I want **to configure pm6 settings via environment variables and config files**,
so that **I can set API credentials and defaults without hardcoding**.

## Acceptance Criteria

### AC1: API Key Loading
**Given** a developer has a `.env` file with `ANTHROPIC_API_KEY`
**When** they instantiate pm6
**Then** the API key is loaded automatically via pydantic-settings
**And** no credentials appear in code

### AC2: Database Path Configuration
**Given** a developer wants to configure database path
**When** they set `PM6_DBPATH` environment variable
**Then** simulations are stored at that path
**And** the default is `./db/` if not specified

### AC3: Global Defaults
**Given** a developer wants global defaults
**When** they set `PM6_DEFAULTMODEL` and `PM6_COSTLIMITPERSESSION`
**Then** new simulations use these defaults
**And** individual simulations can override them

## Tasks / Subtasks

- [x] Task 1: Create Settings class with pydantic-settings (AC: 1, 2, 3)
  - [x] Define Settings class extending BaseSettings
  - [x] Configure PM6_ env prefix
  - [x] Add ANTHROPIC_API_KEY with alias
  - [x] Add dbPath with default ./db
  - [x] Add defaultModel and costLimit settings
  - [x] Add getSettings() cached function

- [x] Task 2: Create .env.example template (AC: 1)
  - [x] Document all available env vars
  - [x] Include example values

- [x] Task 3: Verify configuration loading (AC: 1, 2, 3)
  - [x] Test API key loading from .env
  - [x] Test env var overrides
  - [x] Test default values

## Dev Notes

### Architecture Compliance

**Source:** [docs/architecture.md#Configuration-System]

- Uses pydantic-settings v2 for env loading
- PM6_ prefix for all settings
- camelCase field names (map to PM6_FIELDNAME in env)
- Cached singleton via `@lru_cache`

### Implementation Details

The `Settings` class in `src/pm6/config/settings.py` provides:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PM6_",
        env_file=".env",
    )

    anthropicApiKey: str = Field(alias="ANTHROPIC_API_KEY")
    dbPath: Path = Field(default=Path("./db"))
    defaultModel: str = Field(default="claude-sonnet-4-20250514")
    costLimitPerSession: float = Field(default=10.0)
    # ...
```

### References

- [Source: docs/architecture.md#Configuration-System]
- [Source: docs/prd.md#FR37-FR39] - Configuration requirements
- [Source: docs/epics.md#Story-1.2] - User story definition

## Dev Agent Record

### Context Reference

Story context verified from existing implementation.

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- **Brownfield project**: Configuration system already fully implemented
- **All acceptance criteria verified**:
  - AC1: ANTHROPIC_API_KEY loads from .env via alias
  - AC2: PM6_DBPATH env var overrides default ./db
  - AC3: All settings configurable via PM6_ prefixed env vars
- **Note**: Env var names use uppercase field names (PM6_DBPATH not PM6_DB_PATH)

### File List

_Files verified (already existed):_
- src/pm6/config/__init__.py
- src/pm6/config/settings.py (complete Settings class)
- .env.example (template with all settings)

_No modifications required_
