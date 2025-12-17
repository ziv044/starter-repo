# Story 1.4: Anthropic Client Integration

Status: done

## Story

As a **developer**,
I want **pm6 to communicate with Claude models via Anthropic SDK**,
so that **I can get LLM responses for agent interactions**.

## Acceptance Criteria

- [x] AC1: Valid API credentials establish connection
- [x] AC2: Simple messages receive responses with token tracking
- [x] AC3: Invalid credentials raise clear PM6Error

## Completion Notes

- **Brownfield**: AnthropicClient fully implemented
- Features: prompt caching, cost tracking, model routing, rate limiting
- Uses pydantic-settings for API key management
- Integrates with CostTracker and ModelRouter

## Files

- src/pm6/llm/__init__.py
- src/pm6/llm/anthropicClient.py
- src/pm6/llm/rateLimiter.py
