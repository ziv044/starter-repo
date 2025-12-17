---
stepsCompleted: [1, 2, 3, 4]
lastStep: 4
status: 'complete'
inputDocuments:
  - docs/prd.md
  - docs/architecture.md
  - src/simConfigGui/ (existing code)
---

# pm6 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for pm6, decomposing the requirements from the PRD, Architecture, and existing simConfigGui admin portal into implementable stories.

## Requirements Inventory

### Functional Requirements

**Simulation Creation**
- FR1: Developer can describe a simulation in natural language and have pm6 generate the initial setup
- FR2: Developer can define the agents needed for a simulation
- FR3: Developer can specify simulation rules and constraints
- FR4: Developer can configure simulation parameters (mode, complexity, domain)

**Agent System**
- FR5: System can generate agents based on natural language descriptions
- FR6: System can identify which agents are relevant for a given interaction
- FR7: Developer can configure per-agent memory policies (what to remember/forget)
- FR8: Developer can configure per-agent model selection
- FR9: Agents can access tools (database, files) via Claude Skills
- FR10: Agents can update simulation state based on interactions
- FR11: Agents can respond with behavior that reflects real-world dynamics

**State Management**
- FR12: System can persist simulation state to database
- FR13: System can save/load simulation sessions to/from files
- FR14: System can compact context history into summarized key facts
- FR15: System can manage token budgets to stay within context limits
- FR16: Developer can configure state persistence strategy per simulation
- FR17: System can restore a simulation to a previous checkpoint
- FR18: Agents can query stored state to inform responses

**Cost Optimization**
- FR19: System can record sessions with smart hashing for reuse
- FR20: System can check database for stored responses before making LLM calls
- FR21: System can use prompt caching to reduce redundant token usage
- FR22: System can route routine tasks to cheaper models
- FR23: Developer can view cost tracking and usage metrics
- FR24: System can provide cost estimates before executing expensive operations

**Session Management**
- FR25: System can record all interactions in a session
- FR26: Developer can replay recorded sessions for testing
- FR27: Developer can branch from any point in a session
- FR28: User can return to a simulation later and resume from saved state
- FR29: System can export session data for analysis

**Developer API**
- FR30: Developer can initialize a simulation via API call
- FR31: Developer can send user input and receive agent responses via API
- FR32: Developer can query simulation state via API
- FR33: Developer can configure cost/model settings via API
- FR34: Developer can access session recordings via API
- FR35: API provides clear error messages and status codes

**Configuration & Setup**
- FR36: Developer can install pm6 via standard Python package management
- FR37: Developer can configure Anthropic API credentials
- FR38: Developer can configure database connection for state persistence
- FR39: Developer can set global defaults for model selection and cost limits

**Testing & Validation**
- FR40: Developer can run agents in test mode without incurring full LLM costs
- FR41: Developer can validate agent responses against expected behavior
- FR42: Developer can replay recorded sessions to verify consistent behavior
- FR43: Developer can mock LLM responses for deterministic testing
- FR44: Developer can run cost simulations before deploying agents
- FR45: Developer can compare agent behavior across different configurations
- FR46: System can log all agent decisions and state changes for debugging
- FR47: Developer can run automated test suites against simulation scenarios

### NonFunctional Requirements

**Performance**
- NFR1: Response times must be tracked and reported for every interaction
- NFR2: Cost per interaction must be logged and visible to developer
- NFR3: DB-hit rate (responses served from cache vs LLM) must be measured
- NFR4: System must provide performance baselines and track improvements over time
- NFR5: Any regression in response time or cost must be detectable via metrics

**Integration**
- NFR6: System must integrate with Anthropic API (Claude models)
- NFR7: System must support prompt caching via Anthropic's caching features
- NFR8: System must integrate with Claude Skills for tool use
- NFR9: System must support configurable database backends for state persistence
- NFR10: System must handle API rate limits gracefully (backoff, queuing)

**Reliability**
- NFR11: State persistence must not lose user session data
- NFR12: System must recover gracefully from interrupted sessions
- NFR13: Database operations must be transactional (no partial state writes)
- NFR14: Session recordings must be complete and replayable
- NFR15: System must provide clear error states (not silent failures)

**Security (Minimal for MVP)**
- NFR16: API credentials must be stored securely (not in code)
- NFR17: Session data must be protected from unauthorized access
- NFR18: Cost limits must be enforceable to prevent runaway API spending

### Additional Requirements

**From Architecture:**
- AR1: Manual project setup with modern Python standards (pyproject.toml, src/ layout)
- AR2: camelCase naming convention for functions, variables, file names
- AR3: PascalCase for classes only
- AR4: Folder-based storage (`./db/{simulation_name}/{agents|sessions|responses}/`)
- AR5: xxHash for all signature computation (speed over crypto)
- AR6: Multi-response collection for variety in cached responses
- AR7: Pydantic models for all configuration
- AR8: Async-first API design with context managers
- AR9: Model routing: Haiku for routine tasks, Sonnet for core interactions
- AR10: Google-style docstrings on public API
- AR11: PM6Error exception hierarchy

**From simConfigGui (Admin Portal - Needs Integration):**
- GUI1: Admin dashboard showing active simulations and quick actions
- GUI2: Simulation CRUD operations via web interface
- GUI3: AI-assisted simulation creation (quick prompt + conversational wizard)
- GUI4: Agent management UI (add, edit, delete agents)
- GUI5: Pipeline debug interface (n8n-style step execution)
- GUI6: Turn management UI (player vs CPU control)
- GUI7: Event injection interface
- GUI8: Test runner interface
- GUI9: World state editor (JSON)
- GUI10: Cache control UI (toggle, clear)
- GUI11: **CRITICAL**: Ensure GUI uses pm6 backend consistently (no duplicate logic)
- GUI12: **CRITICAL**: Align GUI db structure with main pm6 db structure
- GUI13: **DESIGN**: UI/UX improvements needed for admin pages
- GUI14: **DESIGN**: Consistent styling with modern admin patterns

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 6 | Natural language simulation creation (via GUI wizard) |
| FR2 | Epic 1 | Define agents needed for simulation |
| FR3 | Epic 1 | Specify simulation rules and constraints |
| FR4 | Epic 1 | Configure simulation parameters |
| FR5 | Epic 2 | Generate agents from natural language |
| FR6 | Epic 2 | Identify relevant agents per interaction |
| FR7 | Epic 2 | Configure per-agent memory policies |
| FR8 | Epic 2 | Configure per-agent model selection |
| FR9 | Epic 2 | Agents access tools via Claude Skills |
| FR10 | Epic 2 | Agents update simulation state |
| FR11 | Epic 2 | Agents respond with real-world dynamics |
| FR12 | Epic 3 | Persist simulation state to database |
| FR13 | Epic 3 | Save/load sessions to/from files |
| FR14 | Epic 3 | Compact context history |
| FR15 | Epic 3 | Manage token budgets |
| FR16 | Epic 3 | Configure state persistence strategy |
| FR17 | Epic 3 | Restore simulation to checkpoint |
| FR18 | Epic 3 | Agents query stored state |
| FR19 | Epic 4 | Record sessions with smart hashing |
| FR20 | Epic 4 | DB-first lookups before LLM calls |
| FR21 | Epic 4 | Prompt caching integration |
| FR22 | Epic 4 | Route routine tasks to cheaper models |
| FR23 | Epic 4 | Cost tracking and usage metrics |
| FR24 | Epic 4 | Cost estimates before expensive operations |
| FR25 | Epic 3 | Record all interactions in session |
| FR26 | Epic 3 | Replay recorded sessions |
| FR27 | Epic 3 | Branch from any session point |
| FR28 | Epic 3 | Resume from saved state |
| FR29 | Epic 3 | Export session data |
| FR30 | Epic 1 | Initialize simulation via API |
| FR31 | Epic 2 | Send input and receive responses via API |
| FR32 | Epic 2 | Query simulation state via API |
| FR33 | Epic 4 | Configure cost/model settings via API |
| FR34 | Epic 3 | Access session recordings via API |
| FR35 | Epic 5 | Clear error messages and status codes |
| FR36 | Epic 1 | Install via Python package management |
| FR37 | Epic 1 | Configure Anthropic API credentials |
| FR38 | Epic 1 | Configure database connection |
| FR39 | Epic 1 | Set global defaults for models/costs |
| FR40 | Epic 5 | Run agents in test mode |
| FR41 | Epic 5 | Validate agent responses |
| FR42 | Epic 5 | Replay sessions to verify behavior |
| FR43 | Epic 5 | Mock LLM responses for testing |
| FR44 | Epic 5 | Run cost simulations |
| FR45 | Epic 5 | Compare agent behavior across configs |
| FR46 | Epic 5 | Log all agent decisions for debugging |
| FR47 | Epic 5 | Run automated test suites |

### NFR Coverage

| NFR | Epic | Description |
|-----|------|-------------|
| NFR1-5 | Epic 4 | Performance tracking and metrics |
| NFR6-10 | Epic 1, 2, 4 | Integration (Anthropic API, Skills, rate limits) |
| NFR11-15 | Epic 3, 5 | Reliability (no data loss, recovery, transactions) |
| NFR16-18 | Epic 6 | Security (credentials, access control, cost limits) |

### Additional Requirements Coverage

| Req | Epic | Description |
|-----|------|-------------|
| AR1-4 | Epic 1 | Project setup, naming conventions, storage |
| AR5-6 | Epic 4 | Hashing, multi-response caching |
| AR7 | Epic 1, 2 | Pydantic models |
| AR8 | Epic 1, 2 | Async-first API design |
| AR9 | Epic 4 | Model routing (Haiku/Sonnet) |
| AR10-11 | Epic 1 | Docstrings, exception hierarchy |
| GUI1-14 | Epic 6 | Admin portal integration |

## Epic List

### Epic 1: Project Foundation & First Simulation
Developer can install pm6, configure credentials, and create their first basic simulation with agents.

**FRs covered:** FR2, FR3, FR4, FR30, FR36, FR37, FR38, FR39
**Additional:** AR1-AR4, AR7, AR8, AR10, AR11, NFR6

**Key Deliverables:**
- Project structure (pyproject.toml, src/pm6/)
- Configuration system (pydantic-settings)
- Simulation class with basic CRUD
- Agent definition and storage
- Anthropic client integration

---

### Epic 2: Agent Intelligence & Interactions
Developer can create sophisticated agents that respond intelligently, route to appropriate agents, and maintain memory.

**FRs covered:** FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR31, FR32
**Additional:** AR7, AR10, NFR6, NFR7, NFR8

**Key Deliverables:**
- Agent generation from descriptions
- Agent routing/identification
- Memory policy system (FULL, SUMMARY, SELECTIVE, NONE)
- Claude Skills integration for tools
- State update mechanisms

---

### Epic 3: State Persistence & Session Management
Developer can save simulations, resume later, checkpoint/restore, and replay sessions.

**FRs covered:** FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR25, FR26, FR27, FR28, FR29, FR34
**Additional:** AR4, NFR11, NFR12, NFR13, NFR14

**Key Deliverables:**
- Folder-based storage system
- Save/load functionality
- Checkpoint/restore
- Session recording
- Session replay and branching
- Context compaction
- Token budget management

---

### Epic 4: Cost Optimization & Caching
Developer can dramatically reduce costs through DB-first lookups, response caching, and smart model routing.

**FRs covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR33
**Additional:** AR5, AR6, AR9, NFR1, NFR2, NFR3, NFR4, NFR5, NFR10

**Key Deliverables:**
- Signature computation (xxHash)
- Response cache with multi-response storage
- DB-first lookup flow
- Prompt caching (Anthropic cache_control)
- Model routing (Haiku/Sonnet/Opus)
- Cost tracking and metrics
- Rate limit handling

---

### Epic 5: Testing & Validation
Developer can test simulations without LLM costs, mock responses, validate behavior, and run automated test suites.

**FRs covered:** FR35, FR40, FR41, FR42, FR43, FR44, FR45, FR46, FR47
**Additional:** NFR15

**Key Deliverables:**
- Test mode (mock LLM client)
- Response mocking system
- Session replay for validation
- Agent behavior comparison
- Decision logging
- Automated test framework
- Clear error messages

---

### Epic 6: Admin Portal Integration
Admin can manage simulations via web interface that uses pm6 backend consistently.

**FRs covered:** FR1
**Additional:** GUI1-GUI14, NFR16, NFR17, NFR18

**Key Deliverables:**
- Align simConfigGui with pm6 backend (no duplicate logic)
- Unify db structure (GUI12)
- AI-assisted simulation wizard (FR1, GUI3)
- UI/UX improvements (GUI13, GUI14)
- Security: credentials, access control, cost limits

---

## Epic 1: Project Foundation & First Simulation

Developer can install pm6, configure credentials, and create their first basic simulation with agents.

### Story 1.1: Project Setup & Package Structure

As a **developer**,
I want **to install pm6 via pip and have a properly structured Python package**,
So that **I can begin building simulations with a solid foundation**.

**Acceptance Criteria:**

**Given** a developer has cloned the pm6 repository
**When** they run `pip install -e .`
**Then** pm6 is installed as an editable package
**And** `from pm6 import Simulation` works without error

**Given** the project structure exists
**When** examining the src/pm6/ directory
**Then** it follows the src/ layout with `__init__.py` exposing public API
**And** pyproject.toml defines package metadata and dependencies
**And** module files use camelCase naming (e.g., `agentConfig.py`)

**Given** the package is installed
**When** running `python -c "import pm6; print(pm6.__version__)"`
**Then** the version string is displayed

---

### Story 1.2: Configuration System

As a **developer**,
I want **to configure pm6 settings via environment variables and config files**,
So that **I can set API credentials and defaults without hardcoding**.

**Acceptance Criteria:**

**Given** a developer has a `.env` file with `ANTHROPIC_API_KEY`
**When** they instantiate pm6
**Then** the API key is loaded automatically via pydantic-settings
**And** no credentials appear in code

**Given** a developer wants to configure database path
**When** they set `PM6_DB_PATH` environment variable
**Then** simulations are stored at that path
**And** the default is `./db/` if not specified

**Given** a developer wants global defaults
**When** they set `PM6_DEFAULT_MODEL` and `PM6_COST_LIMIT`
**Then** new simulations use these defaults
**And** individual simulations can override them

---

### Story 1.3: Exception Hierarchy & Logging

As a **developer**,
I want **clear exceptions and structured logging**,
So that **I can debug issues and handle errors gracefully**.

**Acceptance Criteria:**

**Given** pm6 encounters an error
**When** the error is raised
**Then** it inherits from `PM6Error` base class
**And** specific errors use appropriate subclasses (`AgentNotFoundError`, `CostLimitError`)

**Given** pm6 is running
**When** operations occur
**Then** logs are written via `logging.getLogger("pm6")`
**And** submodules use child loggers (`pm6.agents`, `pm6.cost`)
**And** log levels follow DEBUG/INFO/WARNING/ERROR conventions

---

### Story 1.4: Anthropic Client Integration

As a **developer**,
I want **pm6 to communicate with Claude models via Anthropic SDK**,
So that **I can get LLM responses for agent interactions**.

**Acceptance Criteria:**

**Given** valid API credentials are configured
**When** pm6 initializes the Anthropic client
**Then** connection is established without error
**And** the client is reusable across multiple calls

**Given** the client is initialized
**When** a simple message is sent
**Then** a response is received from Claude
**And** token usage is tracked

**Given** invalid credentials
**When** attempting to initialize
**Then** a clear `PM6Error` is raised with helpful message

---

### Story 1.5: Simulation Class & Basic CRUD

As a **developer**,
I want **to create, load, and manage simulations via the Simulation class**,
So that **I can work with multiple simulation instances**.

**Acceptance Criteria:**

**Given** a developer wants to create a simulation
**When** they call `Simulation(name="my_sim", dbPath="./db")`
**Then** a new simulation is created
**And** the simulation directory `./db/my_sim/` is created

**Given** a simulation exists on disk
**When** the developer instantiates with the same name
**Then** the existing simulation is loaded
**And** previous state is preserved

**Given** a simulation instance
**When** calling `sim.getStats()`
**Then** basic statistics are returned (turn count, agent count)

---

### Story 1.6: Agent Definition & Storage

As a **developer**,
I want **to define agents with configuration and persist them**,
So that **my simulation has characters/entities to interact with**.

**Acceptance Criteria:**

**Given** a simulation exists
**When** calling `sim.addAgent(AgentConfig(name="pm", role="Prime Minister", ...))`
**Then** the agent is added to the simulation
**And** agent config is saved to `./db/my_sim/agents/pm.json`

**Given** agents exist in a simulation
**When** calling `sim.listAgents()`
**Then** a list of agent names is returned

**Given** an agent name
**When** calling `sim.getAgent("pm")`
**Then** the AgentConfig is returned with all properties
**And** `AgentNotFoundError` is raised if agent doesn't exist

---

### Story 1.7: Simulation Rules & Parameters

As a **developer**,
I want **to configure simulation rules, constraints, and parameters**,
So that **simulations behave according to my specifications**.

**Acceptance Criteria:**

**Given** a simulation
**When** setting parameters via `sim.configure(mode="crisis", complexity="high")`
**Then** parameters are stored and retrievable
**And** parameters persist across sessions

**Given** a simulation with world state
**When** calling `sim.setWorldState({"year": 2024, "crisis": "active"})`
**Then** the world state is stored
**And** `sim.getWorldState()` returns the current state

**Given** simulation constraints
**When** setting rules like max turns or allowed actions
**Then** the simulation enforces these constraints

---

## Epic 2: Agent Intelligence & Interactions

Developer can create sophisticated agents that respond intelligently, route to appropriate agents, and maintain memory.

### Story 2.1: Agent Response via Interact API

As a **developer**,
I want **to send user input and receive agent responses via a simple API**,
So that **I can have conversations with simulation agents**.

**Acceptance Criteria:**

**Given** a simulation with agents configured
**When** calling `response = await sim.interact(agentName="pm", userInput="What is your position?")`
**Then** the agent's response is returned
**And** the response includes content, token usage, and metadata

**Given** an interaction occurs
**When** the response is received
**Then** the turn count is incremented
**And** the interaction is logged for debugging

**Given** an invalid agent name
**When** calling `sim.interact(agentName="unknown", ...)`
**Then** `AgentNotFoundError` is raised

---

### Story 2.2: Agent Generation from Descriptions

As a **developer**,
I want **to generate agent configurations from natural language descriptions**,
So that **I can quickly create agents without manual config**.

**Acceptance Criteria:**

**Given** a natural language description like "A cautious defense minister who prioritizes security"
**When** calling `agent = await sim.generateAgent(description="...")`
**Then** an AgentConfig is created with appropriate role, systemPrompt, and traits
**And** the agent can be added to the simulation

**Given** multiple agents need generation
**When** providing a list of descriptions
**Then** each agent is generated with distinct characteristics
**And** agents don't have conflicting configurations

---

### Story 2.3: Agent Routing & Identification

As a **developer**,
I want **the system to identify which agents are relevant for a given interaction**,
So that **only appropriate agents respond to each situation**.

**Acceptance Criteria:**

**Given** agents with declared situation types (e.g., "crisis", "economic", "diplomatic")
**When** an interaction has a situation type
**Then** only agents matching that situation type are considered
**And** irrelevant agents don't consume resources

**Given** multiple relevant agents
**When** routing is performed
**Then** the most appropriate agent is selected
**And** selection logic is configurable

**Given** no matching agents
**When** routing is attempted
**Then** a fallback agent or error is returned based on configuration

---

### Story 2.4: Memory Policy System

As a **developer**,
I want **to configure per-agent memory policies**,
So that **agents remember (or forget) appropriately**.

**Acceptance Criteria:**

**Given** an agent with `memoryPolicy="FULL"`
**When** interactions occur
**Then** complete history is retained in context

**Given** an agent with `memoryPolicy="SUMMARY"`
**When** history exceeds threshold
**Then** older interactions are compacted to summaries
**And** recent interactions remain detailed

**Given** an agent with `memoryPolicy="SELECTIVE"`
**When** interactions occur
**Then** only specified categories are retained
**And** other content is discarded

**Given** an agent with `memoryPolicy="NONE"`
**When** interactions occur
**Then** no history is retained between turns

---

### Story 2.5: Per-Agent Model Selection

As a **developer**,
I want **to configure which Claude model each agent uses**,
So that **I can balance cost and capability per agent**.

**Acceptance Criteria:**

**Given** an agent with `model="claude-sonnet-4-20250514"`
**When** the agent responds
**Then** the Sonnet model is used

**Given** an agent with `model="claude-haiku-3-5-20241022"`
**When** the agent responds
**Then** the cheaper Haiku model is used

**Given** no model specified
**When** the agent responds
**Then** the simulation's default model is used

---

### Story 2.6: Agent State Updates

As a **developer**,
I want **agents to update simulation state based on their actions**,
So that **the world evolves through interactions**.

**Acceptance Criteria:**

**Given** an agent response that affects world state
**When** the response includes state changes
**Then** world state is updated automatically
**And** `sim.getWorldState()` reflects the changes

**Given** multiple state queries needed
**When** calling `sim.queryState(query="approval_rating")`
**Then** specific state values are returned
**And** agents can access this during response generation

---

### Story 2.7: Claude Skills Tool Integration

As a **developer**,
I want **agents to access tools like database and file operations**,
So that **agents can perform structured actions**.

**Acceptance Criteria:**

**Given** an agent with tools enabled
**When** the agent needs to query data
**Then** Claude Skills are invoked with proper tool definitions
**And** tool results are incorporated into the response

**Given** a tool call fails
**When** the agent receives an error
**Then** the error is handled gracefully
**And** the agent can respond appropriately

---

### Story 2.8: Real-World Dynamic Responses

As a **developer**,
I want **agents to respond with behavior that reflects real-world dynamics**,
So that **simulations feel authentic and unpredictable**.

**Acceptance Criteria:**

**Given** an agent representing a political figure
**When** asked about a controversial topic
**Then** the response reflects the character's known positions
**And** responses vary based on world state context

**Given** the same prompt under different conditions
**When** world state differs (e.g., crisis vs peace)
**Then** agent responses adapt to the context
**And** prompt caching is used where appropriate (NFR7)

---

## Epic 3: State Persistence & Session Management

Developer can save simulations, resume later, checkpoint/restore, and replay sessions.

### Story 3.1: State Persistence to Database

As a **developer**,
I want **simulation state to persist to database automatically**,
So that **no data is lost and state survives restarts**.

**Acceptance Criteria:**

**Given** a simulation with world state and agents
**When** state changes occur
**Then** changes are persisted to `./db/{sim_name}/state/`
**And** persistence is transactional (NFR13)

**Given** the application crashes mid-operation
**When** restarting
**Then** the last consistent state is recovered
**And** no partial writes corrupt the data (NFR11)

---

### Story 3.2: Save/Load Sessions to Files

As a **developer**,
I want **to save and load complete simulation sessions**,
So that **users can resume where they left off**.

**Acceptance Criteria:**

**Given** a simulation in progress
**When** calling `sim.save("my_save")`
**Then** complete state is saved to `./db/{sim_name}/sessions/my_save.json`

**Given** a saved session exists
**When** calling `sim.load("my_save")`
**Then** simulation is restored to exact saved state
**And** all agents, world state, and history are restored

---

### Story 3.3: Checkpoint & Restore

As a **developer**,
I want **to create checkpoints and restore to any previous checkpoint**,
So that **I can explore different decision paths**.

**Acceptance Criteria:**

**Given** a simulation at turn 10
**When** calling `checkpoint = sim.createCheckpoint()`
**Then** a checkpoint ID is returned
**And** complete state is captured

**Given** a valid checkpoint ID
**When** calling `sim.restoreCheckpoint(checkpoint)`
**Then** simulation returns to that exact state
**And** subsequent interactions continue from there

---

### Story 3.4: Session Recording

As a **developer**,
I want **all interactions to be recorded in a session log**,
So that **I can analyze and replay sessions**.

**Acceptance Criteria:**

**Given** interactions occur in a simulation
**When** each turn completes
**Then** the interaction is recorded with timestamp, input, output, and state changes
**And** recordings are complete and replayable (NFR14)

**Given** a session with multiple turns
**When** accessing the recording
**Then** all turns are available in sequence
**And** metadata includes token usage and timing

---

### Story 3.5: Session Replay

As a **developer**,
I want **to replay recorded sessions**,
So that **I can verify behavior and debug issues**.

**Acceptance Criteria:**

**Given** a recorded session
**When** calling `sim.replay(sessionId)`
**Then** the session plays back turn by turn
**And** original responses can be compared to new responses

**Given** replay is in progress
**When** pausing at a specific turn
**Then** the simulation state at that turn is accessible
**And** I can inspect agent decisions

---

### Story 3.6: Session Branching

As a **developer**,
I want **to branch from any point in a session**,
So that **I can explore "what if" scenarios**.

**Acceptance Criteria:**

**Given** a session at turn 5
**When** calling `newSim = sim.branchFrom(turnNumber=3)`
**Then** a new simulation is created from turn 3 state
**And** the original session remains unchanged

**Given** a branched simulation
**When** continuing with different inputs
**Then** a new timeline is created
**And** both timelines are independently accessible

---

### Story 3.7: Context Compaction

As a **developer**,
I want **the system to compact context history into summaries**,
So that **long sessions don't exceed context limits**.

**Acceptance Criteria:**

**Given** an agent with history exceeding threshold
**When** compaction is triggered
**Then** older interactions are summarized using cheaper model (Haiku)
**And** key facts are preserved

**Given** compacted history
**When** the agent responds
**Then** summaries provide sufficient context
**And** response quality is maintained

---

### Story 3.8: Token Budget Management

As a **developer**,
I want **the system to manage token budgets**,
So that **context limits are never exceeded**.

**Acceptance Criteria:**

**Given** a context approaching token limit
**When** preparing the next interaction
**Then** content is prioritized (recent > old, relevant > irrelevant)
**And** total tokens stay within budget

**Given** token budget configuration
**When** setting `sim.setTokenBudget(maxTokens=8000)`
**Then** all interactions respect this limit
**And** warnings are logged when approaching limit

---

### Story 3.9: Persistence Strategy Configuration

As a **developer**,
I want **to configure state persistence strategies per simulation**,
So that **I can optimize for my use case**.

**Acceptance Criteria:**

**Given** persistence options (immediate, batched, manual)
**When** setting `sim.setPersistenceStrategy("batched")`
**Then** changes are batched for efficiency

**Given** an agent that needs to query stored state (FR18)
**When** calling `agent.queryState(key="approval")`
**Then** the latest persisted value is returned
**And** queries are efficient

---

### Story 3.10: Session Export

As a **developer**,
I want **to export session data for analysis**,
So that **I can process sessions in external tools**.

**Acceptance Criteria:**

**Given** a recorded session
**When** calling `sim.exportSession(sessionId, format="json")`
**Then** complete session data is exported
**And** format includes all interactions, states, and metadata

**Given** export for analysis
**When** requesting CSV format
**Then** tabular data is exported (turns, tokens, costs)

---

## Epic 4: Cost Optimization & Caching

Developer can dramatically reduce costs through DB-first lookups, response caching, and smart model routing.

### Story 4.1: Signature Computation

As a **developer**,
I want **the system to compute structural signatures for interactions**,
So that **similar interactions can be identified for caching**.

**Acceptance Criteria:**

**Given** an interaction with agent, situation type, state, and input
**When** computing the signature
**Then** xxHash is used for speed (AR5)
**And** signature combines: agent_name + situation_type + state_bucket + input_intent

**Given** similar but not identical inputs
**When** signatures are computed
**Then** state bucketing converts continuous values to ranges
**And** similar situations share signatures for reuse

---

### Story 4.2: Response Cache Storage

As a **developer**,
I want **responses stored with multiple options per signature**,
So that **cached responses have variety**.

**Acceptance Criteria:**

**Given** a new response for a signature
**When** storing the response
**Then** it's added to the collection for that signature
**And** stored in `./db/{sim_name}/responses/{signature}.json`

**Given** multiple responses exist for a signature
**When** retrieving a cached response
**Then** one is selected randomly for variety (AR6)
**And** selection can be configured (random, weighted, etc.)

---

### Story 4.3: DB-First Lookup Flow

As a **developer**,
I want **the system to check cache before making LLM calls**,
So that **costs are minimized**.

**Acceptance Criteria:**

**Given** an incoming interaction
**When** processing begins
**Then** signature is computed first
**And** cache is checked before any LLM call

**Given** a cache hit
**When** a matching response exists
**Then** the cached response is returned
**And** no LLM tokens are consumed

**Given** a cache miss
**When** no matching response exists
**Then** LLM is called
**And** new response is stored with signature

---

### Story 4.4: Prompt Caching Integration

As a **developer**,
I want **Anthropic's prompt caching to reduce token costs**,
So that **repeated context doesn't cost full price**.

**Acceptance Criteria:**

**Given** system prompts that are reused
**When** making API calls
**Then** `cache_control` is set on system prompts
**And** cached tokens cost significantly less

**Given** agent definitions that are stable
**When** multiple interactions occur
**Then** agent prompts are cached across calls
**And** expected savings ~90% on repeated context

---

### Story 4.5: Model Routing

As a **developer**,
I want **routine tasks routed to cheaper models**,
So that **costs are optimized per task type**.

**Acceptance Criteria:**

**Given** a context compaction task
**When** summarizing history
**Then** Haiku model is used (AR9)

**Given** a core agent interaction
**When** generating responses
**Then** Sonnet model is used by default

**Given** complex reasoning required
**When** configured for high-quality output
**Then** Opus model can be selected

---

### Story 4.6: Cost Tracking & Metrics

As a **developer**,
I want **complete visibility into costs and performance**,
So that **I can optimize my simulations**.

**Acceptance Criteria:**

**Given** interactions occur
**When** checking metrics
**Then** response times are tracked per interaction (NFR1)
**And** cost per interaction is logged (NFR2)
**And** DB-hit rate is measured (NFR3)

**Given** historical data exists
**When** viewing performance
**Then** baselines are established (NFR4)
**And** regressions are detectable (NFR5)

---

### Story 4.7: Cost Estimation

As a **developer**,
I want **cost estimates before expensive operations**,
So that **I can make informed decisions**.

**Acceptance Criteria:**

**Given** a planned interaction
**When** calling `estimate = sim.estimateCost(agentName, input)`
**Then** token estimate and cost projection are returned
**And** cache probability is included

**Given** batch operations planned
**When** estimating costs
**Then** aggregate estimates are provided
**And** warnings shown if exceeding budget

---

### Story 4.8: Cost/Model Settings API

As a **developer**,
I want **to configure cost and model settings at runtime**,
So that **I can adjust optimization strategies**.

**Acceptance Criteria:**

**Given** a running simulation
**When** calling `sim.setCostSettings(maxCostPerTurn=0.01)`
**Then** cost limits are enforced
**And** `CostLimitError` raised if exceeded

**Given** model preferences
**When** calling `sim.setModelPreferences(default="haiku", complex="sonnet")`
**Then** routing rules are updated
**And** changes take effect immediately

---

### Story 4.9: Rate Limit Handling

As a **developer**,
I want **graceful handling of API rate limits**,
So that **simulations don't fail under load**.

**Acceptance Criteria:**

**Given** API rate limit is hit
**When** a request fails with 429
**Then** exponential backoff is applied (NFR10)
**And** request is retried automatically

**Given** sustained high load
**When** requests exceed limits
**Then** requests are queued
**And** order is preserved

---

## Epic 5: Testing & Validation

Developer can test simulations without LLM costs, mock responses, validate behavior, and run automated test suites.

### Story 5.1: Test Mode & Mock LLM Client

As a **developer**,
I want **to run agents in test mode without incurring LLM costs**,
So that **I can rapidly iterate and test without burning API credits**.

**Acceptance Criteria:**

**Given** test mode is enabled via `sim.setTestMode(enabled=True)`
**When** agents interact
**Then** a mock LLM client is used instead of Anthropic API
**And** no API calls are made

**Given** test mode with mock client
**When** interactions occur
**Then** responses are generated from configured mocks
**And** all other simulation logic executes normally

**Given** switching out of test mode
**When** `sim.setTestMode(enabled=False)`
**Then** real API calls resume
**And** transition is seamless

---

### Story 5.2: Response Mocking System

As a **developer**,
I want **to mock LLM responses for deterministic testing**,
So that **my tests are repeatable and predictable**.

**Acceptance Criteria:**

**Given** a mock configuration
**When** setting `sim.setMockResponses({"pm": ["Response A", "Response B"]})`
**Then** agent "pm" returns mocked responses in sequence
**And** responses cycle when exhausted

**Given** conditional mocking needed
**When** setting mocks with patterns `sim.setMockResponse(agent="pm", pattern="budget", response="...")`
**Then** pattern-matched inputs return configured responses
**And** unmatched inputs fall through to default mock

**Given** mock recording enabled
**When** running real interactions
**Then** responses can be captured for later mocking
**And** captured responses are saved for test fixtures

---

### Story 5.3: Agent Response Validation

As a **developer**,
I want **to validate agent responses against expected behavior**,
So that **I can ensure agents behave correctly**.

**Acceptance Criteria:**

**Given** expected behavior rules for an agent
**When** defining `sim.addValidation(agent="pm", rules=[...])`
**Then** each response is checked against rules
**And** validation failures are reported

**Given** validation rules include content checks
**When** responses are validated
**Then** rules can check for required phrases, forbidden content, tone
**And** rule violations are logged with details

**Given** validation in CI/CD
**When** tests run with validation enabled
**Then** validation failures cause test failures
**And** detailed reports are generated

---

### Story 5.4: Session Replay for Testing

As a **developer**,
I want **to replay recorded sessions to verify consistent behavior**,
So that **I can detect regressions and validate changes**.

**Acceptance Criteria:**

**Given** a previously recorded session
**When** calling `results = await sim.replayForValidation(sessionId)`
**Then** each turn is replayed
**And** new responses are compared to original

**Given** replay comparison
**When** responses differ from recorded
**Then** differences are highlighted
**And** semantic similarity is measured (not just string match)

**Given** replay validation in tests
**When** differences exceed threshold
**Then** test fails with detailed diff report
**And** acceptable variance is configurable

---

### Story 5.5: Cost Simulation

As a **developer**,
I want **to run cost simulations before deploying agents**,
So that **I can predict and budget API spending**.

**Acceptance Criteria:**

**Given** a simulation configuration
**When** calling `projection = sim.simulateCosts(turnCount=100)`
**Then** estimated costs are calculated
**And** projection includes cache hit assumptions

**Given** cost simulation with scenarios
**When** running multiple configurations
**Then** comparative costs are provided
**And** recommendations for optimization are suggested

**Given** cost limits configured
**When** projection exceeds budget
**Then** warnings are displayed
**And** suggestions to reduce costs are provided

---

### Story 5.6: Agent Behavior Comparison

As a **developer**,
I want **to compare agent behavior across different configurations**,
So that **I can evaluate changes before deploying**.

**Acceptance Criteria:**

**Given** two agent configurations (original vs modified)
**When** calling `comparison = await sim.compareAgents(configA, configB, inputs=[...])`
**Then** both configurations are run against same inputs
**And** responses are compared side-by-side

**Given** comparison results
**When** viewing differences
**Then** similarity scores are provided
**And** significant behavioral changes are highlighted

**Given** A/B testing scenario
**When** running comparison
**Then** statistical significance is calculated for differences
**And** confidence levels are reported

---

### Story 5.7: Decision Logging

As a **developer**,
I want **all agent decisions and state changes logged for debugging**,
So that **I can understand exactly what happened in any interaction**.

**Acceptance Criteria:**

**Given** debug logging enabled via `sim.setLogLevel("DEBUG")`
**When** interactions occur
**Then** all decisions are logged to `pm6.decisions` logger
**And** state changes are captured with before/after values

**Given** a problematic interaction
**When** reviewing logs
**Then** complete decision chain is visible
**And** tool calls, routing decisions, state updates are all logged

**Given** log export needed
**When** calling `sim.exportDecisionLog(sessionId)`
**Then** structured log is exported
**And** format supports analysis tools

---

### Story 5.8: Automated Test Framework

As a **developer**,
I want **to run automated test suites against simulation scenarios**,
So that **I can ensure quality in CI/CD pipelines**.

**Acceptance Criteria:**

**Given** test scenarios defined in `tests/scenarios/`
**When** calling `pytest tests/` or `sim.runTestSuite()`
**Then** all scenarios are executed
**And** results are reported in standard format

**Given** test scenario definition
**When** creating a scenario
**Then** YAML/JSON format specifies inputs, expected outcomes, validations
**And** scenarios can reference recorded sessions as baselines

**Given** CI/CD integration
**When** tests run in pipeline
**Then** exit codes reflect pass/fail
**And** test reports are generated (JUnit XML compatible)

---

### Story 5.9: Clear Error Messages

As a **developer**,
I want **clear error messages and status codes throughout the system**,
So that **I can quickly diagnose and fix issues**.

**Acceptance Criteria:**

**Given** any pm6 error occurs
**When** the error is raised
**Then** message clearly explains what went wrong
**And** message includes actionable guidance

**Given** API errors
**When** status codes are returned
**Then** codes follow HTTP conventions (4xx for client errors, 5xx for server errors)
**And** error responses include error codes, messages, and details

**Given** silent failures are forbidden (NFR15)
**When** any operation fails
**Then** failure is always reported explicitly
**And** no operation fails without trace

---

## Epic 6: Admin Portal Integration

Admin can manage simulations via web interface that uses pm6 backend consistently.

### Story 6.1: Backend Consistency Integration (CRITICAL)

As an **admin**,
I want **the GUI to use pm6 backend consistently without duplicate logic**,
So that **the admin portal and core engine stay synchronized**.

**Acceptance Criteria:**

**Given** simConfigGui Flask application
**When** any simulation operation is performed
**Then** it calls pm6 backend methods directly (e.g., `Simulation.create()`, `sim.addAgent()`)
**And** no duplicate business logic exists in GUI code

**Given** the GUI imports pm6
**When** `from pm6 import Simulation, AgentConfig`
**Then** imports work without errors
**And** all pm6 public API is accessible

**Given** GUI and backend share models
**When** agent or simulation data is modified
**Then** Pydantic models from pm6 are used
**And** no separate model definitions in GUI

---

### Story 6.2: Database Structure Alignment (CRITICAL)

As an **admin**,
I want **GUI and pm6 to share the same database structure**,
So that **data is consistent across both interfaces**.

**Acceptance Criteria:**

**Given** pm6 uses folder-based storage (`./db/{sim_name}/`)
**When** GUI accesses simulation data
**Then** GUI reads/writes to same folder structure
**And** no separate GUI database exists

**Given** simConfigGui's current db structure
**When** aligning with pm6 structure
**Then** migration is performed for existing data
**And** GUI and CLI access same simulations

**Given** a simulation created via GUI
**When** accessed via pm6 CLI/API
**Then** full simulation data is available
**And** vice versa (CLI-created accessible in GUI)

---

### Story 6.3: Admin Dashboard

As an **admin**,
I want **a dashboard showing active simulations and quick actions**,
So that **I can monitor and manage the system at a glance**.

**Acceptance Criteria:**

**Given** admin navigates to dashboard
**When** page loads
**Then** list of all simulations is displayed
**And** each shows: name, status, turn count, last activity

**Given** dashboard with simulations
**When** clicking a simulation
**Then** detailed view opens
**And** quick actions available (run, pause, export)

**Given** dashboard metrics
**When** viewing stats
**Then** total simulations, total agents, API usage shown
**And** data refreshes periodically

---

### Story 6.4: Simulation CRUD Operations

As an **admin**,
I want **to create, read, update, and delete simulations via web interface**,
So that **I can manage simulations without using CLI**.

**Acceptance Criteria:**

**Given** admin clicks "New Simulation"
**When** form is completed
**Then** pm6 `Simulation()` is called
**And** new simulation appears in list

**Given** a simulation exists
**When** admin views details
**Then** full configuration is displayed
**And** all agents and state are visible

**Given** a simulation
**When** admin clicks "Delete"
**Then** confirmation is requested
**And** pm6 `sim.delete()` removes all data

---

### Story 6.5: AI-Assisted Simulation Wizard

As an **admin**,
I want **to create simulations using natural language via AI wizard**,
So that **I can describe what I want and have pm6 generate the setup**.

**Acceptance Criteria:**

**Given** admin opens simulation wizard
**When** entering "Political crisis simulation with PM and cabinet"
**Then** AI generates simulation configuration
**And** suggested agents, rules, and parameters are shown

**Given** wizard generates suggestions
**When** admin reviews
**Then** each suggestion can be accepted, modified, or rejected
**And** conversational refinement is available

**Given** wizard completion
**When** admin approves configuration
**Then** simulation is created via pm6 backend
**And** all generated agents are added

---

### Story 6.6: Agent Management UI

As an **admin**,
I want **to add, edit, and delete agents via web interface**,
So that **I can configure agent rosters visually**.

**Acceptance Criteria:**

**Given** a simulation detail view
**When** clicking "Add Agent"
**Then** agent configuration form opens
**And** form matches AgentConfig Pydantic model fields

**Given** existing agent
**When** clicking "Edit"
**Then** current configuration is editable
**And** changes save via `sim.updateAgent()`

**Given** agent list
**When** clicking "Delete" on an agent
**Then** confirmation is requested
**And** `sim.removeAgent()` is called

---

### Story 6.7: Turn Management & Pipeline Debug

As an **admin**,
I want **UI for managing turns and debugging pipeline execution**,
So that **I can control simulation flow and debug issues**.

**Acceptance Criteria:**

**Given** simulation with player/CPU agents
**When** viewing turn management
**Then** current turn, next agent, and queue are displayed
**And** manual turn advancement is available

**Given** pipeline execution
**When** steps execute
**Then** n8n-style step visualization shows progress
**And** each step's input/output is inspectable

**Given** pipeline debugging
**When** a step fails
**Then** error is highlighted
**And** retry options are available

---

### Story 6.8: World State & Event Management

As an **admin**,
I want **to view/edit world state and inject events**,
So that **I can manipulate simulation conditions**.

**Acceptance Criteria:**

**Given** a running simulation
**When** opening state editor
**Then** current world state JSON is displayed
**And** inline editing is available

**Given** world state editor
**When** admin modifies JSON and saves
**Then** `sim.setWorldState()` is called
**And** validation errors are shown for invalid JSON

**Given** event injection interface
**When** admin creates an event
**Then** event is injected into simulation
**And** agents react appropriately in next turn

---

### Story 6.9: Test Runner & Cache Control

As an **admin**,
I want **to run tests and control caching from the GUI**,
So that **I can validate and optimize simulations**.

**Acceptance Criteria:**

**Given** test runner interface
**When** admin clicks "Run Tests"
**Then** test scenarios execute
**And** results are displayed (pass/fail with details)

**Given** cache control UI
**When** viewing cache stats
**Then** hit rate, cached responses count, storage size shown
**And** toggle to enable/disable caching available

**Given** cache management
**When** admin clicks "Clear Cache"
**Then** response cache is cleared
**And** confirmation shows space reclaimed

---

### Story 6.10: UI/UX Design Improvements

As an **admin**,
I want **a polished, modern admin interface**,
So that **the portal is pleasant and efficient to use**.

**Acceptance Criteria:**

**Given** admin portal
**When** viewing any page
**Then** consistent styling is applied (colors, typography, spacing)
**And** modern admin design patterns are used (sidebar nav, cards, tables)

**Given** forms and actions
**When** interacting
**Then** loading states, success messages, error toasts are shown
**And** UX follows accessibility best practices

**Given** responsive design
**When** accessing on different devices
**Then** layout adapts appropriately
**And** core functionality works on mobile
