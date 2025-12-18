# PM Crisis Simulation - UX Architecture Specification

## Executive Summary

This document specifies the user experience architecture for the Prime Minister crisis simulation interface. The design moves away from chat-based interaction toward **Document Theater** - where the player experiences the simulation through formal government communications, official requests, and structured decision interfaces.

---

## Design Principles

### 1. **Government Formality**
Everything the PM sees is an official document - no casual chat. Even urgent crisis updates arrive as formal situation reports with letterheads, classification stamps, and proper formatting.

### 2. **Decision Clarity**
Each document type maps to a clear interaction pattern:
- Read & Acknowledge (information)
- Approve / Deny (authorization)
- Select One Option (strategic choices)
- Agree / Disagree per item (stakeholder demands)
- Authorize / Defer (operations)

### 3. **Time Pressure**
The interface communicates urgency through:
- Color-coded priority badges (CRITICAL red, HIGH orange, etc.)
- Elapsed time counter
- Pending item count
- Operation progress bars

### 4. **Chief of Staff as Narrator**
The CoS doesn't just aggregate - they *curate and contextualize*. Their narrative frames each turn's documents, highlights conflicts between advisors, and recommends priorities.

---

## Document Type System

### Type 1: SITUATION REPORT (SITREP)
**Source:** Crisis Narrator, Intelligence Briefer
**Interaction:** Read → Acknowledge
**Visual:** News ticker style or classified brief format

```
+----------------------------------------------------------+
| [CLASSIFIED] SITUATION REPORT                    [SECRET] |
| From: Intelligence Briefer | Time: 06:30 Oct 7, 2023     |
+----------------------------------------------------------+
| Hamas militants have breached the border at multiple     |
| points. Estimated 2,000+ fighters inside Israeli         |
| territory. Rocket barrages ongoing.                      |
|                                                          |
| KEY DEVELOPMENTS:                                        |
| - Kibbutz Be'eri under active assault                   |
| - Re'im music festival attacked - mass casualties        |
| - Communication with southern communities lost           |
+----------------------------------------------------------+
|                              [ACKNOWLEDGED ✓]            |
+----------------------------------------------------------+
```

### Type 2: AUTHORIZATION REQUEST
**Source:** IDF Chief of Staff, Defense Minister, Mossad
**Interaction:** Approve ✓ / Deny ✗
**Visual:** Formal request document with letterhead

```
+----------------------------------------------------------+
| [IDF LOGO]  ISRAEL DEFENSE FORCES                        |
|             Chief of Staff                      [URGENT] |
+----------------------------------------------------------+
| AUTHORIZATION REQUEST                                    |
| Ref: IDF-2023-1007-001                                   |
+----------------------------------------------------------+
| Subject: Emergency Reserve Mobilization                  |
|                                                          |
| Request authorization for immediate mobilization of      |
| 300,000 reserve soldiers under Emergency Protocol 7.     |
|                                                          |
| PROJECTED IMPACT:                                        |
| Military Readiness    +25                                |
| Coalition Stability   +10                                |
| International Pressure +5                                |
|                                                          |
| This request requires immediate attention.               |
+----------------------------------------------------------+
| [✓ APPROVE]                          [✗ DENY]           |
+----------------------------------------------------------+
```

### Type 3: TACTICAL OPTIONS
**Source:** Military advisors, Intelligence chiefs
**Interaction:** Select exactly ONE option
**Visual:** Options card with impacts for each choice

```
+----------------------------------------------------------+
| STRATEGIC OPTIONS                    [DECISION REQUIRED] |
| From: IDF Chief of Staff                                 |
+----------------------------------------------------------+
| Multiple response approaches available. Select one:      |
|                                                          |
| ○ OPTION A: Immediate Ground Response                   |
|   Deploy rapid response teams to affected areas          |
|   Impact: Military +15, Civilian Risk +10                |
|                                                          |
| ○ OPTION B: Defensive Consolidation                     |
|   Secure perimeter, evacuate civilians first             |
|   Impact: Civilian Safety +20, Military -5              |
|                                                          |
| ○ OPTION C: Combined Arms Response                      |
|   Air support with limited ground insertion              |
|   Impact: Military +10, International Pressure +15       |
|                                                          |
+----------------------------------------------------------+
|                              [CONFIRM SELECTION]         |
+----------------------------------------------------------+
```

### Type 4: STAKEHOLDER DEMANDS
**Source:** Coalition partners, Hostage families, Public opinion
**Interaction:** Agree/Disagree on EACH demand independently
**Visual:** Petition-style list with individual toggles

```
+----------------------------------------------------------+
| [RIBBON] FORMAL DEMANDS                         [URGENT] |
| From: Hostage Families Representative                    |
+----------------------------------------------------------+
| We present the following demands on behalf of 240        |
| families whose loved ones are held captive:              |
|                                                          |
| 1. Begin immediate negotiations for hostage release      |
|    [AGREE]  [DISAGREE]                                   |
|    Impact if agreed: Families +20, Coalition -10         |
|                                                          |
| 2. Prioritize hostage safety over military objectives    |
|    [AGREE]  [DISAGREE]                                   |
|    Impact if agreed: Hostage Risk -15, Military -10      |
|                                                          |
| 3. Establish direct channel with Hamas negotiators       |
|    [AGREE]  [DISAGREE]                                   |
|    Impact if agreed: Diplomatic +10, Far-Right -20       |
|                                                          |
| ⚠ WARNING: Mass demonstration planned if demands ignored |
+----------------------------------------------------------+
|                              [SUBMIT RESPONSES]          |
+----------------------------------------------------------+
```

### Type 5: OPERATION PROPOSAL
**Source:** Mossad, IDF, Shabak
**Interaction:** Authorize → Track progress / Defer
**Visual:** Mission dossier with timeline

```
+----------------------------------------------------------+
| [MOSSAD LOGO]  OPERATION PROPOSAL            [TOP SECRET] |
+----------------------------------------------------------+
| CODENAME: SILENT FREQUENCY                               |
| Category: [SIGINT]                                       |
+----------------------------------------------------------+
| OBJECTIVE:                                               |
| Exploit cellular tower vulnerabilities in northern Gaza  |
| to intercept Hamas command communications.               |
|                                                          |
| TIMELINE:                                                |
| ⏱ Estimated Duration: 72 hours                          |
|                                                          |
| EXPECTED OUTCOME:                                        |
| Real-time access to Hamas military communications,       |
| enabling advance warning of planned operations.          |
|                                                          |
+----------------------------------------------------------+
| [✓ AUTHORIZE]                        [DEFER TO LATER]    |
+----------------------------------------------------------+
```

When authorized, shows progress:
```
| OPERATION STATUS: IN PROGRESS                            |
| ████████████░░░░░░░░░░░░░░░░░░░░ 37%                     |
| 27h elapsed / 72h total | ETA: 45 hours                  |
| [ABORT OPERATION]                                        |
```

### Type 6: INTELLIGENCE UPDATE (INFO)
**Source:** Any agent
**Interaction:** Acknowledge only (no decision)
**Visual:** Brief update card

```
+----------------------------------------------------------+
| [i] INTELLIGENCE UPDATE                    [CONFIDENTIAL] |
| From: Shabak Director | 07:15                            |
+----------------------------------------------------------+
| Confirmed: Attack originated from Khan Younis command    |
| hub. Yahya Sinwar personally oversaw final preparations. |
| Additional Iranian Revolutionary Guard advisors          |
| identified at planning sessions.                         |
+----------------------------------------------------------+
|                              [ACKNOWLEDGED]              |
+----------------------------------------------------------+
```

---

## Screen Layout Architecture

### Main Interface Layout
```
+------------------------------------------------------------------------+
|  [SEAL] STATE OF ISRAEL - PRIME MINISTER'S OFFICE            [LOGOUT] |
|  Turn 1 | October 7, 2023 06:30 | Hours Elapsed: 0    [PHASE: CRISIS] |
+------------------------------------------------------------------------+
|                                    |                                   |
|  INCOMING DOCUMENTS (3)            |  NATIONAL STATUS                  |
|  --------------------------------  |  -------------------------------- |
|  [!] Authorization - IDF           |  Military Readiness    [████  ] 75%|
|  [!] Demands - Hostage Families    |  Coalition Stability   [█████ ] 80%|
|  [i] SITREP - Intelligence         |  Public Morale         [████  ] 75%|
|                                    |  International         [██    ] 25%|
|  ACTIVE OPERATIONS (1)             |  Hostages Held              240  |
|  --------------------------------  |                                   |
|  SILENT FREQ [████░░░░] 37%        |  FRONT STATUS                    |
|                                    |  Gaza: ⚔ ACTIVE COMBAT           |
|                                    |  Lebanon: 🔵 QUIET                |
|                                    |  West Bank: 🟡 TENSE              |
|                                    |                                   |
+------------------------------------+-----------------------------------+
|                                                                        |
|  CHIEF OF STAFF BRIEFING                                              |
|  -------------------------------------------------------------------- |
|  "Prime Minister, the situation is unprecedented. The IDF is          |
|   requesting emergency mobilization - I recommend approval. The       |
|   hostage families are demanding immediate negotiations, which        |
|   conflicts with the far-right ministers' position. You'll need       |
|   to balance these carefully. Mossad has a SIGINT operation ready     |
|   that could give us crucial intelligence within 72 hours."           |
|                                                                        |
|  [VIEW IDF REQUEST] [VIEW DEMANDS] [VIEW OPERATION]                   |
|                                                                        |
+------------------------------------------------------------------------+
|                                                                        |
|  +-----------------------------------------------------------------+  |
|  | [CURRENT DOCUMENT - Full detail view of selected item]          |  |
|  | ...                                                             |  |
|  +-----------------------------------------------------------------+  |
|                                                                        |
|  AVAILABLE ADVISORS - Request Meeting (+7 hours each)                 |
|  [IDF Chief] [Mossad] [Defense Min] [Shabak] [US SecState]           |
|                                                                        |
|  [PROCEED TO NEXT TURN →]  (Disabled until mandatory items resolved)  |
+------------------------------------------------------------------------+
```

---

## Agent Response Format

To enable this UX, agents must output in a **hybrid format** combining narrative and structured data.

### Agent Output Schema
```yaml
response:
  # Executive summary for CoS aggregation
  summary: "IDF requesting 300K reserve mobilization for emergency response"

  # Narrative content (displayed in full document view)
  narrative: |
    **IMMEDIATE TACTICAL ASSESSMENT**

    The scale of infiltration exceeds anything in our contingency planning...

  # Structured action items
  action_items:
    - type: approval
      title: "Emergency Reserve Mobilization"
      content: "Request authorization for 300,000 reserve callup"
      urgency: critical
      impacts:
        military_readiness: 25
        coalition_stability: 10
        international_pressure: 5

    - type: option
      title: "Initial Response Strategy"
      options:
        - id: "immediate"
          text: "Immediate ground response"
          impacts: { military_readiness: 15, civilian_risk: 10 }
        - id: "consolidate"
          text: "Defensive consolidation"
          impacts: { civilian_safety: 20, military_readiness: -5 }
```

### Response Format Instructions for Agents

Add to agent system prompts:
```
When responding, structure your output as follows:

1. EXECUTIVE SUMMARY (1-2 sentences)
   A brief summary of your key point for the Chief of Staff's briefing.

2. DETAILED NARRATIVE
   Your full assessment, recommendations, or demands in your character's voice.

3. ACTION ITEMS (if any)
   End with structured items using these formats:

   For authorization requests:
   [AUTHORIZATION REQUEST]
   Title: <title>
   Content: <what you're requesting>
   Urgency: critical/high/medium/low
   Impacts: <metric>: <+/- value>, ...

   For options:
   [OPTIONS]
   Title: <decision title>
   1. <option text> | Impacts: <metric>: <value>, ...
   2. <option text> | Impacts: <metric>: <value>, ...

   For operations:
   [OPERATION PROPOSAL]
   Codename: <name>
   Category: cyber/kinetic/humint/sigint/recon/rescue
   Duration: <hours>
   Description: <what the operation does>
   Expected Outcome: <success criteria>
```

---

## Chief of Staff Aggregation Layer

The CoS synthesizes agent outputs into a cohesive briefing:

### CoS Responsibilities

1. **Priority Ordering**: Present items by urgency (critical → high → medium → low)

2. **Conflict Detection**: Identify when agents disagree
   - "The Defense Minister recommends immediate action, but the US Secretary urges restraint"

3. **Narrative Framing**: Provide context
   - "This is the largest security breach in Israel's history..."

4. **Recommendation**: Suggest which documents to address first
   - "I recommend addressing the IDF authorization request immediately"

### CoS Output Format
```yaml
cos_briefing:
  turn_number: 1
  game_time: "October 7, 2023 06:30"
  hours_elapsed: 0

  opening_narrative: |
    Prime Minister, we are in crisis. At 06:30 this morning, Hamas launched
    a multi-pronged assault from Gaza. Initial reports indicate over 250
    casualties with the number rising. Multiple kibbutzim are under attack.

  conflicts_detected:
    - agents: ["Defense Minister", "US Secretary of State"]
      issue: "Scale of military response"
      summary: "Defense wants maximum force; US urging restraint"

  priority_items:
    - type: approval
      source: "IDF Chief of Staff"
      summary: "Reserve mobilization request"
      urgency: critical
    - type: demands
      source: "Hostage Families"
      summary: "3 demands regarding negotiations"
      urgency: high

  advisor_recommendations:
    - "Address IDF authorization immediately - military readiness critical"
    - "The far-right ministers will react strongly if you engage Hamas"

  closing: |
    I've organized the incoming documents by priority. The IDF request
    cannot wait. What would you like to address first?
```

---

## Implementation Priorities

### Phase 1: Agent Output Enhancement
1. Update agent system prompts to output structured format
2. Enhance `CosParser` to extract structured blocks
3. Test with existing agents

### Phase 2: CoS Aggregation
1. Create `CosBriefingGenerator` class
2. Implement conflict detection algorithm
3. Add priority sorting logic

### Phase 3: Frontend Redesign
1. Create document-based layout (replacing chat)
2. Implement document type components
3. Add CoS narrative panel
4. Build active operations tracker

### Phase 4: Polish
1. Add visual effects (document stamps, seals)
2. Implement sound cues for urgent items
3. Add animation for incoming documents
4. Test full turn flow

---

## Technical Notes

### Existing Infrastructure to Leverage
- `ActionItem` types in `action_items.py` - fully compatible
- `action_cards.css` - government document styling ready
- `cos_view.html` - action items sections exist but aren't populated

### Key Changes Needed
1. **Agent prompts**: Add structured output format
2. **CosParser**: Enhance to extract structured blocks (not just NLP inference)
3. **CoS agent**: Change from "aggregator" to "briefing generator"
4. **Frontend**: Replace briefs list with document queue

### State Management
- `pending_documents[]` - Queue of unprocessed documents
- `active_operations[]` - Operations being tracked
- `cos_briefing` - Current turn's briefing
- `world_state` - Game metrics (already exists)

---

## Appendix: Document Visual Mockups

See wireframes in: `docs/wireframes/`

### Color Scheme
- Header bars: Navy blue (#1e3a5f) for Israeli government
- Critical urgency: Red (#dc3545)
- High urgency: Orange (#ff9800)
- Success/Approve: Green (#28a745)
- Deny/Reject: Gray (#6c757d)
- Classification stamps: Red background, white text

### Typography
- Headers: Bold, uppercase for formality
- Body: Clear sans-serif for readability
- Classification badges: Small caps, letter-spacing

---

*Document prepared by Winston (Architect Agent)*
*Version 1.0 - December 2024*
