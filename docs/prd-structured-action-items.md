# PRD: Structured Action Items System (Epic 9)

## Overview

Transform raw agent outputs into structured, actionable items with different interaction patterns and persistence. The Chief of Staff parses natural language agent responses and presents them as interactive document-style cards with real consequences.

---

## Problem Statement

**Current State:**
- Agents produce natural language responses (IDF briefs, Mossad proposals, family demands)
- Information flows past the player as text and disappears
- No tracking of proposed operations, pending approvals, or unanswered demands
- Player has no clear actions to take beyond "proceed to decision"

**Desired State:**
- Agent outputs are classified into actionable item types
- Each type has specific interaction patterns (approve/deny, agree/disagree, select one)
- Items persist until resolved
- Operations are tracked over time with progress indicators
- Player sees consequences BEFORE deciding

---

## User Stories

### Story 9.1: Action Item Classification System

**As** the Chief of Staff agent,
**I want** to parse agent responses and classify content into structured action items,
**So that** the player receives clear, actionable information.

**Classification Types:**

| Type | Description | Interaction | Persistence |
|------|-------------|-------------|-------------|
| `INFO` | Status updates, situational awareness | Display only | None |
| `METRIC_UPDATE` | World state changes | Auto-apply | Applied to state |
| `APPROVAL` | Authorization requests | Approve / Deny | Until decided |
| `DEMAND` | Stakeholder demands | Agree / Disagree (each) | Until responded |
| `OPTION` | Choose one from multiple | Radio select | Until chosen |
| `OPERATION` | Time-bound operations | Authorize → Track | Active until complete |

**Acceptance Criteria:**
- [ ] ActionItem dataclass with type, source_agent, content, status fields
- [ ] CoS uses LLM to parse agent responses into ActionItems
- [ ] Classification prompt extracts structured data reliably
- [ ] Items stored in CosPlayState for persistence across turns

---

### Story 9.2: Approval Request Flow

**As** a player,
**I want** to see authorization requests as official document cards,
**So that** I can approve or deny with full impact visibility.

**Card Structure:**
```
┌─────────────────────────────────────────────┐
│ [LOGO] ENTITY NAME                   [BADGE]│
│        AUTHORIZATION REQUEST                │
├─────────────────────────────────────────────┤
│ Request Title                    timestamp  │
│ ─────────────────────────────────────────── │
│ Request description and rationale           │
│                                             │
│ PROJECTED IMPACT                            │
│ ┌─────────────────────────────────────────┐ │
│ │ Metric1 +X │ Metric2 +Y │ Metric3 -Z   │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ [████ APPROVE ████]  [░░░░ DENY ░░░░]      │
└─────────────────────────────────────────────┘
```

**Acceptance Criteria:**
- [ ] ApprovalCard component renders with entity header (logo, name, badge)
- [ ] Impact preview shows color-coded metrics (green +, red -)
- [ ] Approve applies predicted impacts to world state
- [ ] Deny removes item with no state change (or negative relationship impact)
- [ ] Classification badges: CONFIDENTIAL (red), URGENT (yellow), ROUTINE (blue)

---

### Story 9.3: Demand Response Flow

**As** a player,
**I want** to respond to stakeholder demands individually,
**So that** I can balance competing interests strategically.

**Card Structure:**
```
┌─────────────────────────────────────────────┐
│ [LOGO] STAKEHOLDER NAME              [URGENT]│
│        FORMAL DEMANDS                        │
├─────────────────────────────────────────────┤
│ X families/groups demand action:             │
│                                              │
│ 1. Demand text          [Agree] [Disagree]  │
│    Impact: Agree +X/-Y | Disagree -Z        │
│                                              │
│ 2. Demand text          [Agree] [Disagree]  │
│    Impact: Agree +X/-Y | Disagree -Z        │
│                                              │
│ ⚠️ Warning: Upcoming consequence             │
│                                              │
│ [████████ SUBMIT RESPONSES ████████]        │
└─────────────────────────────────────────────┘
```

**Acceptance Criteria:**
- [ ] DemandCard component renders multiple demands from single source
- [ ] Each demand has independent Agree/Disagree toggle
- [ ] Impact preview per demand shown inline
- [ ] Submit applies all selected responses at once
- [ ] Warning banner shows time-sensitive consequences

---

### Story 9.4: Operation Proposal and Tracking

**As** a player,
**I want** to authorize operations that execute over game time,
**So that** strategic decisions have realistic timelines.

**Proposal Card:**
```
┌─────────────────────────────────────────────┐
│ [LOGO] AGENCY NAME              [TOP SECRET]│
│        OPERATION PROPOSAL                   │
├─────────────────────────────────────────────┤
│ Operation CODENAME                          │
│ [CATEGORY BADGE: CYBER/KINETIC/HUMINT]     │
│ ─────────────────────────────────────────── │
│ Operation description                       │
│                                             │
│ TIMELINE                                    │
│ ┌─────────────────────────────────────────┐ │
│ │ ⏱️ Initial: 48-72h  │  Full: 2-3 weeks │ │
│ │ Progress: ░░░░░░░░░░░░░░░░░░░░ 0%      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ EXPECTED OUTCOME                            │
│ [Success enables new options/intelligence]  │
│                                             │
│ [████ AUTHORIZE OP ████]  [░░░ DEFER ░░░]  │
└─────────────────────────────────────────────┘
```

**Active Operation Card (in sidebar):**
```
┌─────────────────────────────────────────────┐
│ Op SILENT FREQUENCY              [ACTIVE]   │
│ Owner: Mossad | Started: Turn 1             │
│ Progress: ████████░░░░░░░░░░░░░░ 33%       │
│ ETA: 48h remaining                          │
│ [Cancel] [Details]                          │
└─────────────────────────────────────────────┘
```

**Acceptance Criteria:**
- [ ] OperationCard component with timeline visualization
- [ ] Category badges (CYBER, KINETIC, HUMINT, SIGINT, RECON)
- [ ] On authorize: create ActiveOperation with duration, owner, start time
- [ ] Progress bar updates each turn based on game time elapsed
- [ ] On completion: trigger completion event, notify owning agent
- [ ] Active operations shown in sidebar with progress
- [ ] Operations can be cancelled (with consequences)

---

### Story 9.5: Operation Lifecycle Management

**As** the simulation engine,
**I want** to track active operations and trigger events on completion,
**So that** time-based decisions have meaningful follow-through.

**Operation States:**
```
PROPOSED → AUTHORIZED → IN_PROGRESS → [COMPLICATION?] → COMPLETED/FAILED/CANCELLED
```

**Data Model:**
```python
@dataclass
class ActiveOperation:
    id: str
    name: str
    codename: str
    category: Literal["cyber", "kinetic", "humint", "sigint", "recon"]
    owner_agent: str
    description: str

    # Timeline
    duration_hours: int
    started_at: datetime
    estimated_completion: datetime

    # Progress
    hours_elapsed: int = 0
    progress_percent: float = 0.0
    status: Literal["in_progress", "completed", "failed", "cancelled"] = "in_progress"

    # Outcome
    completion_event: str | None = None  # Event to trigger on completion
    expected_outcome: str = ""

    # Complications
    complication_chance: float = 0.1
    complication_event: str | None = None
```

**Acceptance Criteria:**
- [ ] ActiveOperation dataclass with full lifecycle fields
- [ ] OperationsTracker class manages all active operations
- [ ] Each turn: update hours_elapsed, progress_percent for all ops
- [ ] On completion: trigger completion_event, notify agent
- [ ] Random complication check each turn (optional)
- [ ] CoS briefing includes active operations summary
- [ ] Owning agent receives operation context in their prompts

---

### Story 9.6: CoS Parsing Pipeline

**As** the Chief of Staff,
**I want** to parse agent responses into structured action items,
**So that** natural language becomes actionable UI.

**Parsing Flow:**
```
Agent Response (natural language)
    ↓
CoS Parsing Prompt
    ↓
Structured JSON extraction
    ↓
ActionItem creation
    ↓
Validation & deduplication
    ↓
Add to CosPlayState.pending_items
```

**Parsing Prompt Template:**
```
You are parsing an agent's response to extract structured action items.

Agent: {agent_name} ({agent_role})
Response: {agent_response}

Extract ALL of the following that apply:

1. INFO items - pure status updates, no action needed
2. METRIC_UPDATES - specific numbers that should update world state
3. APPROVAL_REQUESTS - things requiring PM authorization
4. DEMANDS - stakeholder demands with agree/disagree options
5. OPTIONS - multiple choices where PM must pick one
6. OPERATIONS - proposed time-bound operations with durations

Output JSON:
{
  "items": [
    {
      "type": "approval",
      "title": "Reserve Mobilization",
      "content": "Request authorization for 300,000 reserve callup",
      "impacts": {"military_readiness": 25, "coalition_stability": 10},
      "urgency": "high"
    },
    {
      "type": "operation",
      "codename": "SILENT FREQUENCY",
      "category": "cyber",
      "description": "Cellular tower infiltration in northern Gaza",
      "duration_hours": 72,
      "expected_outcome": "Hamas communication intercept capability"
    }
  ]
}
```

**Acceptance Criteria:**
- [ ] CoS parsing method accepts agent name + response text
- [ ] LLM extracts structured items with consistent schema
- [ ] Validation ensures required fields present
- [ ] Deduplication prevents duplicate items across agents
- [ ] Items tagged with source_agent for attribution

---

### Story 9.7: Enhanced CoS Briefing UI

**As** a player,
**I want** to see all pending actions in an organized, immersive layout,
**So that** I feel like I'm in a real situation room.

**Screen Layout:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CHIEF OF STAFF BRIEFING    [Turn X]   Date/Time   Hours: Y   [PHASE]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ TICKER: Military | Coalition | Hostages | Int'l | Morale | Active Ops | ⚠️  │
├──────────────────────────────────────────────────────┬──────────────────────┤
│                                                      │                      │
│  [FLASH ALERT / EVENT NARRATIVE]                    │   ADVISORS           │
│                                                      │   [Meet buttons]     │
│  PENDING ACTIONS (N)                                 │                      │
│  ┌────────┐  ┌────────┐  ┌────────┐                 │   ACTIVE OPERATIONS  │
│  │Approval│  │Operation│  │Demand │                 │   [Progress cards]   │
│  │ Card   │  │ Card    │  │ Card  │                 │                      │
│  └────────┘  └────────┘  └────────┘                 │                      │
│                                                      │                      │
│  INTELLIGENCE UPDATES                                │   [PROCEED BTN]      │
│  [Info cards - display only]                         │                      │
└──────────────────────────────────────────────────────┴──────────────────────┘
```

**Acceptance Criteria:**
- [ ] Ticker bar shows live world state metrics with change indicators
- [ ] Pending actions count badge with urgency coloring
- [ ] Cards grouped by type (approvals, operations, demands)
- [ ] Info cards displayed separately (no action needed)
- [ ] Active operations sidebar with progress bars
- [ ] "Proceed to Decision" only enabled when mandatory items resolved
- [ ] Responsive layout for different screen sizes

---

## Technical Implementation

### New Files to Create

| File | Purpose |
|------|---------|
| `src/pm6/core/action_items.py` | ActionItem, ActiveOperation dataclasses |
| `src/pm6/core/operations_tracker.py` | OperationsTracker class |
| `src/pm6/core/cos_parser.py` | CoS parsing pipeline |
| `src/simConfigGui/templates/play/components/` | Card components (Jinja2 partials) |
| `src/simConfigGui/static/css/action-cards.css` | Card styling |
| `src/simConfigGui/static/js/action-items.js` | Card interactions |

### Files to Modify

| File | Changes |
|------|---------|
| `src/pm6/core/cos_mode.py` | Integrate parsing, track pending items |
| `src/pm6/core/engine.py` | Update operations each turn |
| `src/pm6/core/types.py` | Add ActionItem types |
| `src/simConfigGui/routes/play.py` | Add action item endpoints |
| `src/simConfigGui/templates/play/cos_view.html` | New layout with cards |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/cos/items` | GET | List all pending action items |
| `/cos/items/<id>/approve` | POST | Approve an approval request |
| `/cos/items/<id>/deny` | POST | Deny an approval request |
| `/cos/demands/<id>/respond` | POST | Submit demand responses |
| `/cos/options/<id>/select` | POST | Select an option |
| `/cos/operations` | GET | List active operations |
| `/cos/operations/<id>/cancel` | POST | Cancel an operation |

---

## Wireframes

See: `docs/wireframes/`
- `approval-card-idf.excalidraw`
- `operation-card-mossad.excalidraw`
- `demand-card-hostages.excalidraw`
- `cos-briefing-full-screen.excalidraw`

---

## Success Metrics

1. **Clarity**: Player understands available actions without reading walls of text
2. **Persistence**: No action items "disappear" - all are tracked until resolved
3. **Consequence Visibility**: Impact preview accuracy > 90%
4. **Operation Follow-through**: 100% of authorized operations trigger completion events
5. **Immersion**: Player feedback indicates "situation room" feel

---

## Dependencies

- Epic 8 (CoS Mode) must be complete - ✅ DONE
- Play Mode event system - ✅ DONE
- World state management - ✅ DONE

---

## Open Questions

1. **Complication system**: Should operations have random complications? (Deferred to v2)
2. **Operation cancellation cost**: What's the penalty for cancelling mid-operation?
3. **Demand escalation**: Do ignored demands escalate over time?

---

## Status

- [x] Requirements gathered
- [x] UX wireframes created
- [ ] PRD approved
- [ ] Implementation started
