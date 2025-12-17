# Story 1.2: Configuration System

**Status:** ready-for-dev
**Epic:** Epic 1 - Project Foundation & First Simulation
**Story Key:** 1-2-configuration-system

## Story

As a **developer**,
I want **to configure pm6 settings via environment variables and config files**,
So that **I can set API credentials and defaults without hardcoding**.

## Acceptance Criteria

- [ ] AC1: A `.env` file with `ANTHROPIC_API_KEY` loads automatically via pydantic-settings and no credentials appear in code
- [ ] AC2: `PM6_DB_PATH` environment variable configures simulation storage path with default `./db/` if not specified
- [ ] AC3: `PM6_DEFAULT_MODEL` and `PM6_COST_LIMIT` (session/interaction) are configurable globally and overridable per simulation

## Implementation Context

### Brownfield Status

This is a **brownfield project** - the configuration system already exists. This story documents verification of the existing implementation against acceptance criteria.

### Existing Implementation Analysis

**Configuration Files (Verified):**
```
pm6/
├── .env.example           # Template with all config options
├── .env                   # Local configuration (gitignored)
└── src/pm6/config/
    ├── __init__.py        # Exports Settings, getSettings
    └── settings.py        # pydantic-settings implementation
```

### Key Implementation: `src/pm6/config/settings.py`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PM6_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Configuration
    anthropicApiKey: str = Field(
        default="",
        alias="ANTHROPIC_API_KEY",  # Loads from ANTHROPIC_API_KEY directly
        description="Anthropic API key",
    )

    # Storage Configuration
    dbPath: Path = Field(
        default=Path("./db"),
        description="Path to database storage directory",
    )

    # Model Configuration
    defaultModel: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default model for agent responses",
    )
    compactionModel: str = Field(
        default="claude-haiku-3-20240307",
        description="Model for context compaction",
    )

    # Cost Limits
    costLimitPerSession: float = Field(default=10.0)
    costLimitPerInteraction: float = Field(default=1.0)

    # Logging
    logLevel: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

@lru_cache
def getSettings() -> Settings:
    """Get cached singleton Settings instance."""
    return Settings()
```

### Environment Variables Mapping

| Environment Variable | Settings Field | Default | Purpose |
|---------------------|----------------|---------|---------|
| `ANTHROPIC_API_KEY` | `anthropicApiKey` | `""` | Claude API access |
| `PM6_DB_PATH` | `dbPath` | `./db` | Storage directory |
| `PM6_DEFAULT_MODEL` | `defaultModel` | `claude-sonnet-4-20250514` | Agent responses |
| `PM6_COMPACTION_MODEL` | `compactionModel` | `claude-haiku-3-20240307` | Context compaction |
| `PM6_COST_LIMIT_PER_SESSION` | `costLimitPerSession` | `10.0` | Max USD/session |
| `PM6_COST_LIMIT_PER_INTERACTION` | `costLimitPerInteraction` | `1.0` | Max USD/interaction |
| `PM6_LOG_LEVEL` | `logLevel` | `INFO` | Logging verbosity |

### .env.example Template

```bash
# pm6 Configuration
ANTHROPIC_API_KEY=your_api_key_here

# Storage Configuration
PM6_DB_PATH=./db

# Model Configuration
PM6_DEFAULT_MODEL=claude-sonnet-4-20250514
PM6_COMPACTION_MODEL=claude-haiku-3-20240307

# Cost Limits (optional)
PM6_COST_LIMIT_PER_SESSION=10.0
PM6_COST_LIMIT_PER_INTERACTION=1.0

# Logging
PM6_LOG_LEVEL=INFO
```

### Architecture Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| AR7: Pydantic models | Implemented | `Settings(BaseSettings)` |
| NFR16: Secure credentials | Implemented | Loaded from env, not in code |
| NFR18: Cost limits | Implemented | `costLimitPerSession`, `costLimitPerInteraction` |

## Tasks

### Verification Tasks

- [ ] 1. Verify API key loading
  - [ ] 1.1 Confirm `ANTHROPIC_API_KEY` loads from .env
  - [ ] 1.2 Verify key is not hardcoded anywhere
  - [ ] 1.3 Test Settings instantiation without key (should not fail)

- [ ] 2. Verify database path configuration
  - [ ] 2.1 Test default `./db/` path
  - [ ] 2.2 Test custom `PM6_DB_PATH` override
  - [ ] 2.3 Verify `ensureDbPath()` creates directory

- [ ] 3. Verify model and cost settings
  - [ ] 3.1 Confirm `PM6_DEFAULT_MODEL` loads correctly
  - [ ] 3.2 Confirm cost limits load correctly
  - [ ] 3.3 Test settings override mechanism

- [ ] 4. Verify singleton behavior
  - [ ] 4.1 Confirm `getSettings()` returns cached instance
  - [ ] 4.2 Verify `@lru_cache` prevents re-initialization

### Validation Commands

```bash
# AC1: API key loading (should show empty or actual key from .env)
python -c "from pm6.config.settings import getSettings; s = getSettings(); print(f'API key loaded: {bool(s.anthropicApiKey)}')"

# AC2: Database path
python -c "from pm6.config.settings import getSettings; s = getSettings(); print(f'DB path: {s.dbPath}')"

# AC3: Model and cost settings
python -c "
from pm6.config.settings import getSettings
s = getSettings()
print(f'Default model: {s.defaultModel}')
print(f'Cost limit/session: {s.costLimitPerSession}')
print(f'Cost limit/interaction: {s.costLimitPerInteraction}')
"

# Test environment variable override
PM6_DB_PATH=/tmp/test_db python -c "from pm6.config.settings import Settings; s = Settings(); print(f'Override DB path: {s.dbPath}')"
```

## Technical Notes

### pydantic-settings Pattern

The configuration uses `pydantic-settings` v2.x with:
- **env_prefix**: `PM6_` prefix for all settings (except aliases)
- **env_file**: `.env` file support
- **alias**: Special handling for `ANTHROPIC_API_KEY` (no prefix needed)

### Singleton Pattern

`getSettings()` uses `@lru_cache` to ensure:
- Single initialization on first call
- Cached instance returned on subsequent calls
- Thread-safe access

### Security Considerations

- API keys loaded from environment, never hardcoded
- `.env` file is in `.gitignore`
- `.env.example` provides template without real values

## Previous Story Context

From **Story 1.1** (Project Setup):
- Package structure established at `src/pm6/`
- `pydantic-settings>=2.0.0` added to dependencies
- camelCase naming convention applies to Settings fields

## Definition of Done

- [ ] All acceptance criteria verified
- [ ] Settings load from environment variables
- [ ] API key loads from `ANTHROPIC_API_KEY`
- [ ] Database path defaults to `./db/`
- [ ] Cost limits are configurable
- [ ] Singleton pattern working correctly
- [ ] Tests pass: `pytest tests/test_config/ -v`

## Dev Agent Record

### File List
- [src/pm6/config/settings.py](../../src/pm6/config/settings.py) - Main configuration implementation
- [src/pm6/config/__init__.py](../../src/pm6/config/__init__.py) - Module exports
- [.env.example](../../.env.example) - Configuration template

### Change Log
- Story created for brownfield verification
- All acceptance criteria pre-verified against existing implementation
- Configuration system fully implemented with pydantic-settings
