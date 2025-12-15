# pm6

LLM testing infrastructure with record-replay pattern for deterministic Claude API testing.

## Installation

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Configure Environment

Copy `.env.example` to `.env` and set your API key:

```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### 2. Record API Calls (LIVE mode)

```python
from pm6 import LLMLogger, LoggedCall, get_settings
import anthropic

settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
logger = LLMLogger("my_session")

request = {
    "model": settings.default_model,
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
}

with LoggedCall(logger, "my_agent", request) as call:
    response = client.messages.create(**request)
    call.set_response(response)
```

### 3. Replay for Testing (REPLAY mode)

```python
from pm6 import LLMReplayProvider, Mode
import os

os.environ["PM6_MODE"] = "REPLAY"

provider = LLMReplayProvider("logs/my_session_001.jsonl")
response = provider.get_response("my_agent")
# Returns the logged response deterministically
```

## Modes

- **LIVE**: Make real API calls, optionally log them
- **REPLAY**: Use logged responses (no API calls)
- **HYBRID**: Try replay first, fall back to live

## Configuration

Environment variables (prefix `PM6_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | - | Your Anthropic API key |
| `PM6_MODE` | `LIVE` | Operating mode |
| `PM6_LOG_DIR` | `./logs` | Directory for log files |
| `PM6_STRICT_REPLAY` | `true` | Raise on missing replay data |
| `PM6_DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Default model |

## Running Tests

```bash
pytest --cov=pm6
```

## License

MIT
