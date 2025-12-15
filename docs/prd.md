---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - docs/research-cicd.md
documentCounts:
  briefs: 0
  research: 1
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
lastStep: 11
status: 'complete'
project_name: 'pm6'
user_name: 'Ziv04'
date: '2025-12-15'
---

# Product Requirements Document - pm6

**Author:** Ziv04
**Date:** 2025-12-15

## Executive Summary

**pm6** is a reusable Python backend project template designed for rapid initialization of agent-powered applications. It provides pre-built infrastructure for Claude API integration, eliminating the repetitive setup work that slows down iterative development cycles.

### Vision

A clean, minimal codebase that can be loaded in seconds - not hours. Each iteration of a new project starts from a solid, tested foundation rather than rebuilding the same infrastructure repeatedly.

### What Makes This Special

- **Iteration-friendly**: Built for developers who prototype fast, learn, and restart fresh
- **Pre-wired infrastructure**: CI/CD (GitHub Actions), testing (pytest), agent support - all ready
- **Extensible foundation**: New "should-be-basic" functions get added as patterns emerge
- **Focused scope**: Only essential infrastructure - no bloat, no over-engineering

## Project Classification

**Technical Type:** developer_tool (SDK/library)
**Domain:** general (AI infrastructure)
**Complexity:** low-medium
**Project Context:** Greenfield - new project

### Technical Foundation
- **Language:** Python 3.12
- **API:** Anthropic Claude SDK
- **Testing:** pytest + pytest-cov + pytest-asyncio
- **CI/CD:** GitHub Actions with branch protection
- **Philosophy:** Minimal, test-driven, iterative

## Success Criteria

### User Success

- **5-Minute Setup**: Clone pm6, run `pip install`, infrastructure ready
- **Zero Rebuild**: LLMLogger, LLMReplayProvider, agent config system ready
- **Instant Testing**: Run `pytest` with replay mode - no API costs, deterministic results
- **CI/CD Ready**: Push to GitHub, tests run automatically

### Business Success

- **Faster Iteration Cycles**: Next project starts with solid foundation
- **Focus on Value**: Time spent on YOUR agents, not infrastructure plumbing
- **Confidence to Restart**: Clean foundation means no fear of "starting fresh"

### Technical Success

- **Replay System Working**: LLMLogger captures, LLMReplayProvider replays
- **Per-Agent Mode Config**: Each agent can be set to live/replay/hybrid independently
- **CI Pipeline Green**: GitHub Actions runs pytest on every push
- **Branch Protection Active**: PRs require passing tests to merge

### Measurable Outcomes

| Metric | Target |
|--------|--------|
| Time to working infrastructure | < 5 minutes |
| Test suite passes | 100% on clone |
| API calls needed for testing | 0 (replay mode) |

## Product Scope

### MVP - Minimum Viable Product

1. **LLMLogger** - Log all Claude API calls to JSONL per session
2. **LLMReplayProvider** - Replay logged responses for deterministic testing
3. **Agent Config System** - Configure each agent's mode (live/replay/hybrid)
4. **Settings/Config** - Environment-based configuration with defaults
5. **pytest setup** - Test suite with replay integration
6. **GitHub Actions** - CI workflow on push/PR

### Growth Features (Post-MVP)

- Additional utilities as patterns emerge from your projects

### Vision (Future)

- Your personal "repo-initializer" that grows with each iteration

## User Journeys

### Journey 1: Ziv - Starting Fresh with Solid Foundation

Ziv has just finished an iteration of his game project. He learned a lot, but the codebase got messy. Time to start fresh.

**The Old Way (Pain):**
Before pm6, starting a new project meant rebuilding the same infrastructure every time - LLMLogger, replay system, pytest config, GitHub Actions. Hours spent on plumbing before writing a single line of actual agent code.

**The New Way (With pm6):**
1. Clone pm6 repo
2. Run `pip install -r requirements.txt`
3. Set `ANTHROPIC_API_KEY` in `.env`
4. Run `pytest` - all tests pass (replay mode, no API calls)
5. Start writing agent code immediately

**The Breakthrough:**
First commit has actual agent logic, not infrastructure setup. Tests run on push. Regressions caught automatically. Focus stays on the game, not the plumbing.

**Result:**
New project starts in 5 minutes. Clean foundation. Confidence to iterate fast.

### Journey Requirements Summary

This journey reveals requirements for:
- **Quick setup**: Clone + pip install = working infrastructure
- **Replay system**: Tests run without API calls
- **CI/CD ready**: GitHub Actions pre-configured
- **Agent config**: Per-agent mode settings (live/replay/hybrid)

## Developer Tool Requirements

### Project-Type Overview

pm6 is a Python developer tool providing infrastructure for agent-powered applications. It's designed for personal use with potential to grow into a reusable template.

### Language & Package Management

| Aspect | Choice |
|--------|--------|
| Language | Python 3.12 |
| Package Manager | pip (requirements.txt) |
| Virtual Environment | Standard venv |

### API Surface

**Core Modules:**

| Module | Purpose |
|--------|---------|
| `LLMLogger` | Log all Claude API calls to JSONL per session |
| `LLMReplayProvider` | Replay logged responses for deterministic testing |
| `Settings` | Environment-based configuration with defaults |
| `AgentConfig` | Per-agent mode configuration (live/replay/hybrid) |

### Installation Method

```bash
git clone <repo>
cd pm6
pip install -r requirements.txt
cp .env.example .env  # Add ANTHROPIC_API_KEY
pytest  # Verify setup
```

### Documentation Strategy

- **Inline docstrings**: For all public functions
- **README.md**: Quick start and basic usage
- **No separate docs site**: Keep it minimal

### Implementation Considerations

- No package publishing (not on PyPI) - clone-and-use pattern
- Tests included and passing from day 1
- CI/CD pre-configured (GitHub Actions)

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Platform MVP - minimal foundation for agent projects
**Team:** Solo developer
**Timeline:** Quick iteration

### MVP Feature Set (Phase 1)

1. **LLMLogger** - Session-based API call logging
2. **LLMReplayProvider** - Deterministic test replay
3. **AgentConfig** - Per-agent mode configuration
4. **Settings** - Environment-based configuration
5. **pytest integration** - Tests use replay by default
6. **GitHub Actions** - CI pipeline pre-configured

### Post-MVP (As Needed)

- Additional utilities discovered through use
- Patterns extracted from future projects
- No planned features - grow organically

### Risk Mitigation

- **Technical Risk:** Low - patterns proven in pm4
- **Scope Creep Risk:** Mitigated by "minimal only" philosophy
- **Time Risk:** Mitigated by extracting from working pm4 code

## Functional Requirements

### Logging Capabilities

- FR1: System can log all Claude API calls to JSONL format
- FR2: System can create session-based log files (one per session)
- FR3: System can auto-increment log file names (game_1.jsonl, game_2.jsonl)
- FR4: System can log request prompt, response, token count, and duration
- FR5: System can associate each log entry with an agent name

### Replay Capabilities

- FR6: System can load recorded JSONL log files for replay
- FR7: System can return recorded responses instead of making live API calls
- FR8: System can operate in LIVE mode (real API calls only)
- FR9: System can operate in REPLAY mode (recorded responses only)
- FR10: System can operate in HYBRID mode (replay with live fallback)
- FR11: System can match replay responses by agent name sequentially
- FR12: System can report replay status (responses remaining per agent)

### Agent Configuration

- FR13: Developer can configure each agent's mode independently
- FR14: Developer can set global default mode for all agents
- FR15: Developer can override global mode per-agent

### Environment Configuration

- FR16: System can load configuration from environment variables
- FR17: System can load configuration from .env file
- FR18: System can provide sensible defaults for all settings
- FR19: Developer can configure Claude model selection
- FR20: Developer can configure log directory path

### Testing Infrastructure

- FR21: System can run tests using replay mode by default
- FR22: System can execute tests without requiring API key (replay mode)
- FR23: Developer can run test suite with single command (pytest)

### CI/CD Infrastructure

- FR24: System can run tests automatically on git push
- FR25: System can run tests automatically on pull request
- FR26: System can block merge if tests fail

## Non-Functional Requirements

### Code Quality & Maintainability

- NFR1: Code follows PEP 8 style guidelines
- NFR2: All public functions have docstrings
- NFR3: Code is formatted with black (line-length 100)
- NFR4: Code passes ruff linting with no errors

### Testability

- NFR5: All tests pass without requiring live API calls
- NFR6: Tests produce identical results on repeated runs (deterministic)
- NFR7: Test suite completes in under 30 seconds

### Integration

- NFR8: Compatible with Anthropic SDK latest stable version
- NFR9: Compatible with pytest 8.x
- NFR10: CI workflow runs on ubuntu-latest GitHub runner

### Security

- NFR11: API keys loaded from environment variables only (never hardcoded)
- NFR12: .env files excluded from git via .gitignore
