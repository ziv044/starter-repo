---
stepsCompleted: [1, 2, 3, 4, 6, 7, 8, 9, 10, 11]
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

**pm6** is an LLM-powered simulation engine designed to be the foundational infrastructure for a new generation of interactive experiences. By combining large language models with simulation mechanics, pm6 enables dynamic, AI-driven scenarios that adapt and respond with unprecedented sophistication.

### Vision

Build the simulation engine first - solid, smart foundations that make everything else possible. Games, training tools, and commercial applications will follow once the core is right.

### What Makes This Special

- **Unprecedented territory:** The gaming + LLM combination hasn't truly happened yet - pm6 is pioneering this space
- **Endless content potential:** LLM-powered simulations create infinite playability and emergent scenarios
- **New gaming concepts:** Level of sophistication that introduces entirely new paradigms in interactive simulation
- **Platform approach:** One well-built engine enables many applications - from Prime Minister simulations to World War scenarios to RPG adventures to professional training

### Target Users

- **Phase 1 (Engine):** Developers and creators building simulation experiences
- **Phase 2 (Applications):** Gamers, LLM enthusiasts, professionals needing training simulations

## Project Classification

**Technical Type:** developer_tool (simulation engine/SDK)
**Domain:** scientific (simulation, ML, AI)
**Complexity:** Medium
**Project Context:** Greenfield - new project

### Technical Foundation

Platform-first architecture: simulation engine core that serves as foundation for diverse applications including gaming, professional training, and creative storytelling.

## Success Criteria

### User Success

- **Natural language simulation setup:** User describes desired simulation in plain language, app drives dialog to capture needed details
- **Agent generation:** System automatically generates appropriate agents based on user requirements
- **Testing capabilities:** Developers can test generated agents before deployment
- **Cost/model configurability:** First-class infrastructure for controlling costs and model selection
- **Outcome:** User inputs desired simulation → dialog captures requirements → custom simulation generated

### Business Success

- **Dual-use platform:** Works for personal simulation building AND as infrastructure others build on
- **Infrastructure-first validation:** Prove the cost-effective, smart, fast foundation works before scaling content
- **Success indicator:** Generates simulations that are cost-effective, smart, fast, and have great content

### Technical Success

- **Cost Optimization Architecture:**
  - Session recording with smart hashing (code-based, not LLM)
  - DB-first approach: use stored responses when possible, LLM only when necessary
  - Agent identification: only activate relevant agents per interaction
  - Anthropic ecosystem integration: Claude Skills, prompt caching, smart context management

- **Performance:** Optimized at every layer for fastest possible response times
- **Clean separation:** Infrastructure completely decoupled from content
- **Lesson applied:** Previous iteration proved content quality is achievable; pm6 proves sustainability

### Measurable Outcomes

| Metric | Target |
|--------|--------|
| Cost per interaction | Lowest possible (DB-first, caching, smart agent selection) |
| Response time | Fast as possible (optimized at every layer) |
| LLM calls avoided | Maximize via hashing + DB lookups |
| Agent relevance | Only necessary agents activated per interaction |

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Platform MVP - Build the sustainable infrastructure foundation

**Core Principle:** Prove that LLM-powered simulations can be cost-effective, fast, and smart before investing in content/games.

**Resource Requirements:** Solo developer (Ziv), Python expertise, Anthropic ecosystem knowledge

### MVP Feature Set (Phase 1) - Revised

**1. State Management Infrastructure**
- State Persistence Layer (DB + file save/load)
- Memory Policy System (configurable per agent - what to remember/forget)
- Context Compaction (smart summarization to avoid context explosion)
- Tool Integration (Claude Skills for DB/file access)
- Token Budget Management (stay within context limits)

**2. Cost Optimization Layer**
- Session recording with smart hashing
- DB-first lookups (stored responses before LLM calls)
- Prompt caching integration
- Cheaper model routing (routine tasks use cheaper models)
- Cost tracking/visibility

**3. Agent Infrastructure**
- Basic agent generation (natural language → agent setup)
- Agent identification (only relevant agents per interaction)
- Per-agent configuration (mode, memory policy, model selection)

### State Management Toolkit

| Tool | Purpose | When to Use |
|------|---------|-------------|
| Database | Persistent state, queryable facts | World state, relationships, history |
| Save Files | Session snapshots, checkpoint/restore | User returns, branching paths |
| Caching | Reuse responses, avoid redundant calls | Similar queries, patterns |
| Cheaper Models | Routine tasks, summarization | Non-critical work, compaction |
| Skills | Structured tool use | DB queries, file operations |
| Compacting | Summarize history into key facts | Long sessions, context overflow |
| Token Management | Optimize what goes in context | Every interaction |

### Post-MVP Features (Phase 2 - Growth)

- Multi-agent orchestration (complex agent interactions)
- Advanced context management strategies
- Model selection flexibility (hot-swap models)
- Claude Skills deep integration
- Performance analytics dashboard

### Future Vision (Phase 3 - Expansion)

- Full simulation generation from single natural language description
- Self-optimizing cost/quality tradeoffs
- Platform for others to build commercial simulations
- Marketplace for simulation templates

### Risk Mitigation Strategy

**Technical Risks:**
- State management complexity → Start with simple DB + file approach, evolve
- Context explosion → Compaction + token management from day 1
- Cost unpredictability → Cost tracking baked in, not bolted on

**Market Risks:**
- LLM gaming doesn't resonate → Infrastructure has value for training, professional tools
- No fallback → Mitigated by modular design, pivot-ready architecture

**Resource Risks:**
- Solo developer → Focus on core infrastructure, avoid feature creep
- Time constraints → MVP philosophy, ship and iterate

## User Journeys

### Journey 1: Ziv - From Expensive Experiments to Sustainable Simulation Engine

Ziv is a DBA and self-taught developer who's already built several apps. He's fascinated by what LLMs could bring to gaming - not just chatbots, but truly dynamic simulations where every playthrough is unique. He envisions Prime Minister simulations, World War scenarios, RPG adventures that actually adapt intelligently.

**The Pain (Previous Iteration):**
He built a prototype. The content was amazing - smart, refined responses that felt alive. But reality hit hard: 50 cents per round, minute-long wait times, and a codebase that became a mess of UX experiments. Worse, he kept asking himself: "How do I make this *playable* and not just walls of text?" The cost alone made it unsustainable to even test properly.

**The Realization:**
After too many restarts, Ziv understands: infrastructure must come first. The content quality is proven - now he needs to prove sustainability. Separate the engine from the simulation. Build once, build right.

**Building pm6:**
He starts fresh with pm6. Session recording with smart hashing. DB-first lookups. Prompt caching. Only the relevant agents activate. He watches the costs drop while the speed climbs. For the first time, he can iterate on gameplay without bleeding money.

**The Breakthrough:**
Ziv describes a simulation in natural language. pm6 generates the agents, sets up the dialog flow, and he's testing within minutes - not hours. The infrastructure handles the complexity; he focuses on making it fun.

**The New Reality:**
pm6 becomes his foundation. Every new simulation idea starts fast, runs cheap, and stays maintainable. The dream of LLM-powered gaming feels achievable.

### Journey 2: Shaked - Finding Games That Actually Think

Shaked is a software engineer who games to unwind - but also to think. He's tired of scripted NPCs, predictable storylines, and "choices" that lead to the same three endings. He craves games that challenge him intellectually, where his decisions actually matter and the world responds intelligently.

**The Frustration:**
Every promising game eventually reveals its limits. The "open world" has invisible walls. The "dynamic AI" follows obvious patterns. He's beaten the system enough times to see the strings behind the puppets. He wants a game where he can't predict what happens next - where the simulation is smarter than his ability to game it.

**Discovery:**
A friend mentions a Prime Minister simulation that's "different." Skeptical but curious, Shaked tries it.

**The Wow Moment:**
He makes a controversial policy decision, expecting the usual canned responses. Instead, the opposition leader reacts with a strategy he didn't anticipate. The media coverage shifts in nuanced ways. An ally distances themselves for reasons that make *sense*. The entities behave with shocking similarity to real-world dynamics. This isn't scripted - it's *thinking*.

**The Hook:**
Every session unfolds differently. He replays the same scenario with different approaches and gets genuinely different outcomes. The endless options to explore keep pulling him back. He starts learning about geopolitics, economics, negotiation - not from a textbook, but from consequence.

**The New Reality:**
For Shaked, pm6-powered simulations aren't just games - they're thinking environments. Deep strategy, infinite replayability, and actual learning disguised as play.

### Journey Requirements Summary

These journeys reveal requirements for:

**From Ziv's Journey (Developer/Creator):**
- Natural language → agent generation
- Session recording with smart hashing
- DB-first lookups to minimize LLM costs
- Prompt caching integration
- Cost tracking and visibility
- Fast iteration cycle (minutes, not hours)
- Clean separation of infrastructure from content

**From Shaked's Journey (End-User):**
- Entities that behave with real-world similarity
- Non-scripted, intelligent responses
- Meaningful consequences for decisions
- Infinite replayability through dynamic content
- Deep enough for strategic thinking
- Educational value through simulation

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. LLM + Gaming Convergence**
pm6 pioneers the intersection of large language models and gaming simulation - a combination that hasn't truly happened yet. While games like Victoria 3 offer deep strategic simulation, they rely on scripted systems. pm6 brings genuine AI-driven dynamic responses to interactive experiences.

**2. New Paradigm: Infrastructure-First LLM Gaming**
Rather than building games that happen to use LLMs, pm6 inverts the approach: build sustainable LLM infrastructure first, then enable games on top. This addresses the fundamental barrier (cost/speed) that has prevented LLM gaming from emerging.

**3. Cost-Optimization as Core Innovation**
The architecture itself is innovative:
- DB-first approach (stored responses before LLM calls)
- Smart hashing to identify reusable content
- Agent identification to activate only relevant agents
- Prompt caching and context management as infrastructure

This makes sustainable LLM-powered simulations possible for the first time.

**4. Natural Language → Simulation Generation**
Users describe simulations in plain language; pm6 generates the appropriate agents and dialog flows. This democratizes simulation creation beyond traditional game developers.

### Market Context & Competitive Landscape

**Closest Existing Product:** Victoria 3 (Paradox Interactive)
- Deep political/economic simulation
- Complex emergent gameplay
- BUT: Scripted systems, predictable patterns once understood

**pm6 Differentiation:**
- LLM-driven responses that genuinely adapt
- Infinite content through AI generation
- Entities that behave with "shocking similarity" to real-world dynamics
- No scripted ceiling - the simulation can surprise even the creator

**Market Gap:** No product currently combines:
- AAA-depth simulation complexity
- LLM-powered dynamic responses
- Sustainable cost model
- Developer-friendly engine approach

### Validation Approach

1. **Cost sustainability proof:** Demonstrate DB-first + caching + smart agents dramatically reduce per-interaction cost
2. **Response quality validation:** Test that LLM responses maintain "real-world similarity" quality
3. **Playability testing:** Validate simulations are engaging, not just walls of text
4. **Speed benchmarks:** Prove response times are acceptable for interactive play

### Risk Mitigation

**Primary Risk:** No fallback position - full commitment to LLM + gaming vision

**Mitigation Strategy:**
- Infrastructure-first approach reduces risk by validating sustainability before content investment
- Modular design allows pivoting to other LLM applications (training, professional tools) if gaming doesn't resonate
- Cost optimization architecture has value regardless of end application

## Developer Tool Requirements

### Project-Type Overview

pm6 is a Python developer tool providing infrastructure for LLM-powered simulations. It follows a "complexity hidden, simplicity exposed" philosophy - sophisticated internal systems (session recording, DB-first lookups, smart hashing, prompt caching) are abstracted behind clean APIs.

### Language & Package Management

| Aspect | Choice |
|--------|--------|
| Language | Python (primary) |
| Multi-language | TBD - evaluate post-MVP |
| Package Manager | Standard Python (pip/poetry) |

### API Surface

**Core Approach:** Expose clean APIs, hide internal complexity

Developers interact with pm6 through APIs rather than understanding internal mechanics. The "secret sauce" (session recording, smart hashing, DB-first lookups, agent identification, prompt caching) operates transparently.

**Developer Experience Goal:**
- Simple API calls to create/run simulations
- Internal optimization happens automatically
- Cost/performance benefits without cognitive overhead

### Installation Method

```bash
git clone <repo>
cd pm6
pip install -r requirements.txt
# or pip install pm6 (if published)
```

### Documentation Strategy

- **Inline docstrings**: For public API functions
- **README.md**: Quick start and basic usage
- **Examples**: Working code samples
- **No heavy docs site**: Keep it minimal, learn by doing

### Implementation Considerations

- API-first design: clean interfaces, hidden internals
- Infrastructure is the product, not just documentation
- Dogfooding: pm6 powers your own simulations first

## Functional Requirements

### Simulation Creation

- FR1: Developer can describe a simulation in natural language and have pm6 generate the initial setup
- FR2: Developer can define the agents needed for a simulation
- FR3: Developer can specify simulation rules and constraints
- FR4: Developer can configure simulation parameters (mode, complexity, domain)

### Agent System

- FR5: System can generate agents based on natural language descriptions
- FR6: System can identify which agents are relevant for a given interaction
- FR7: Developer can configure per-agent memory policies (what to remember/forget)
- FR8: Developer can configure per-agent model selection
- FR9: Agents can access tools (database, files) via Claude Skills
- FR10: Agents can update simulation state based on interactions
- FR11: Agents can respond with behavior that reflects real-world dynamics

### State Management

- FR12: System can persist simulation state to database
- FR13: System can save/load simulation sessions to/from files
- FR14: System can compact context history into summarized key facts
- FR15: System can manage token budgets to stay within context limits
- FR16: Developer can configure state persistence strategy per simulation
- FR17: System can restore a simulation to a previous checkpoint
- FR18: Agents can query stored state to inform responses

### Cost Optimization

- FR19: System can record sessions with smart hashing for reuse
- FR20: System can check database for stored responses before making LLM calls
- FR21: System can use prompt caching to reduce redundant token usage
- FR22: System can route routine tasks to cheaper models
- FR23: Developer can view cost tracking and usage metrics
- FR24: System can provide cost estimates before executing expensive operations

### Session Management

- FR25: System can record all interactions in a session
- FR26: Developer can replay recorded sessions for testing
- FR27: Developer can branch from any point in a session
- FR28: User can return to a simulation later and resume from saved state
- FR29: System can export session data for analysis

### Developer API

- FR30: Developer can initialize a simulation via API call
- FR31: Developer can send user input and receive agent responses via API
- FR32: Developer can query simulation state via API
- FR33: Developer can configure cost/model settings via API
- FR34: Developer can access session recordings via API
- FR35: API provides clear error messages and status codes

### Configuration & Setup

- FR36: Developer can install pm6 via standard Python package management
- FR37: Developer can configure Anthropic API credentials
- FR38: Developer can configure database connection for state persistence
- FR39: Developer can set global defaults for model selection and cost limits

### Testing & Validation

- FR40: Developer can run agents in test mode without incurring full LLM costs
- FR41: Developer can validate agent responses against expected behavior
- FR42: Developer can replay recorded sessions to verify consistent behavior
- FR43: Developer can mock LLM responses for deterministic testing
- FR44: Developer can run cost simulations before deploying agents
- FR45: Developer can compare agent behavior across different configurations
- FR46: System can log all agent decisions and state changes for debugging
- FR47: Developer can run automated test suites against simulation scenarios

## Non-Functional Requirements

### Performance

**Philosophy:** Optimize aggressively, measure continuously

- NFR1: Response times must be tracked and reported for every interaction
- NFR2: Cost per interaction must be logged and visible to developer
- NFR3: DB-hit rate (responses served from cache vs LLM) must be measured
- NFR4: System must provide performance baselines and track improvements over time
- NFR5: Any regression in response time or cost must be detectable via metrics

**Targets (directional, not fixed):**
- Response time: As fast as achievable given cost constraints
- Cost: As low as achievable given quality constraints
- DB-hit rate: Maximize over time through smart hashing

### Integration

- NFR6: System must integrate with Anthropic API (Claude models)
- NFR7: System must support prompt caching via Anthropic's caching features
- NFR8: System must integrate with Claude Skills for tool use
- NFR9: System must support configurable database backends for state persistence
- NFR10: System must handle API rate limits gracefully (backoff, queuing)

### Reliability

- NFR11: State persistence must not lose user session data
- NFR12: System must recover gracefully from interrupted sessions
- NFR13: Database operations must be transactional (no partial state writes)
- NFR14: Session recordings must be complete and replayable
- NFR15: System must provide clear error states (not silent failures)

### Security (Minimal for MVP)

- NFR16: API credentials must be stored securely (not in code)
- NFR17: Session data must be protected from unauthorized access
- NFR18: Cost limits must be enforceable to prevent runaway API spending

