"""Structured Response Format for PM Simulation Agents.

Defines the output format agents should use to enable
document-theater UX instead of chat-based interaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Response format instructions to inject into agent prompts
STRUCTURED_RESPONSE_INSTRUCTIONS = """
## RESPONSE FORMAT

Structure your response in TWO parts:

### PART 1: NARRATIVE
Your character's voice - the full assessment, report, or message as they would deliver it.
This appears in the "full document view" when the PM clicks to read details.

### PART 2: STRUCTURED ITEMS (End of response)
After your narrative, add any action items using these exact formats:

**For Authorization Requests** (things requiring PM approval):
```
[AUTHORIZATION REQUEST]
Title: <short title>
Content: <what you're requesting authorization for>
Urgency: critical|high|medium|low
Impacts: <metric>:<+/-value>, <metric>:<+/-value>
```

**For Strategic Options** (PM must choose one):
```
[OPTIONS]
Title: <decision topic>
1. <option text> | Impacts: <metric>:<value>, <metric>:<value>
2. <option text> | Impacts: <metric>:<value>, <metric>:<value>
3. <option text> | Impacts: <metric>:<value>, <metric>:<value>
```

**For Operations** (time-bound missions you propose):
```
[OPERATION PROPOSAL]
Codename: <OPERATION NAME IN CAPS>
Category: cyber|kinetic|humint|sigint|recon|rescue|diplomatic
Duration: <number> hours
Description: <what the operation does>
Expected Outcome: <what success looks like>
```

**For Demands** (stakeholder demands on the PM):
```
[DEMANDS]
Title: <who is demanding>
Warning: <consequence if ignored, optional>
1. <demand text> | Agree: <metric>:<value> | Disagree: <metric>:<value>
2. <demand text> | Agree: <metric>:<value> | Disagree: <metric>:<value>
```

**For Information Updates** (no action needed, just acknowledgment):
```
[INFO]
Title: <brief title>
Classification: confidential|secret|top_secret
Content: <the information>
```

### METRICS YOU CAN REFERENCE
- military_readiness (0-100)
- coalition_stability (0-100)
- public_morale (0-100)
- international_pressure (0-100, lower is better)
- us_relations (0-100)
- hostage_count (number)
- hostage_risk (0-100, lower is better)
- civilian_casualties_israeli (number)
- civilian_casualties_palestinian (number)
- international_credibility (0-100)

### EXAMPLE RESPONSE

---
Prime Minister, the situation is dire. At 06:30 hours, Hamas launched
a coordinated multi-pronged assault. We have confirmed breaches at
multiple points along the Gaza border.

**IMMEDIATE ASSESSMENT**
- Over 250 casualties confirmed, number rising
- Multiple kibbutzim under active assault
- Air defense systems overwhelmed by rocket volume

I need immediate authorization to mobilize reserves. Without
additional forces, we cannot secure all breach points.

**RECOMMENDATIONS**
1. Authorize emergency reserve mobilization
2. Establish forward command posts
3. Coordinate with Air Force for close support

---
[AUTHORIZATION REQUEST]
Title: Emergency Reserve Mobilization
Content: Request authorization to mobilize 300,000 reserve soldiers under Emergency Protocol 7
Urgency: critical
Impacts: military_readiness:+25, coalition_stability:+10, international_pressure:+5

[OPTIONS]
Title: Initial Response Strategy
1. Immediate ground assault on breach points | Impacts: military_readiness:+15, civilian_risk:+10
2. Defensive perimeter while evacuating civilians | Impacts: civilian_safety:+20, military_readiness:-5
3. Combined arms with air support first | Impacts: military_readiness:+10, international_pressure:+15
---
"""


CHIEF_OF_STAFF_INSTRUCTIONS = """
## YOUR ROLE AS CHIEF OF STAFF

You are the Prime Minister's Chief of Staff. Your job is to:

1. **AGGREGATE** - Collect all advisor inputs for this turn
2. **PRIORITIZE** - Order items by urgency (critical first)
3. **CONTEXTUALIZE** - Frame the situation, highlight conflicts
4. **RECOMMEND** - Suggest which items to address first

## OUTPUT FORMAT

Structure your briefing as follows:

### OPENING NARRATIVE
2-3 sentences setting the stage. What's happening right now?

### ADVISOR SUMMARY
For each advisor who spoke this turn:
- **[Advisor Role]**: <1-2 sentence summary of their position>

### CONFLICTS DETECTED
If advisors disagree, highlight:
- "The [Role A] recommends X, but [Role B] urges Y"

### PRIORITY QUEUE
List action items in priority order:
1. [CRITICAL] <item type> from <source> - <brief description>
2. [HIGH] <item type> from <source> - <brief description>
...

### MY RECOMMENDATION
What should the PM address first and why?

### DOCUMENTS ATTACHED
The structured action items from all advisors (these will be displayed as formal documents).

---

## EXAMPLE BRIEFING

Prime Minister, we are in the most significant security crisis since 1973.
Multiple Hamas units have breached the southern border. Casualty reports
are still coming in but already exceed anything in recent memory.

**ADVISOR POSITIONS:**
- **IDF Chief of Staff**: Requesting immediate reserve mobilization (300K troops).
  Cannot secure all breach points with current forces.
- **Defense Minister**: Coordinating national emergency response. Recommends
  declaring state of war.
- **Mossad Director**: Intelligence failure under investigation. Recommending
  SIGINT operation to intercept Hamas communications.
- **Hostage Families**: Already mobilizing. Demanding immediate negotiations.

**CONFLICT DETECTED:**
- The Defense Minister and Far-Right Ministers want maximum military force
- The Hostage Families are demanding negotiation which conflicts with this

**PRIORITY QUEUE:**
1. [CRITICAL] Authorization Request from IDF - Reserve mobilization
2. [CRITICAL] Demands from Hostage Families - 3 demands requiring response
3. [HIGH] Operation Proposal from Mossad - SIGINT operation (72h)

**MY RECOMMENDATION:**
Address the IDF authorization first - we need troops in the field.
The hostage families' demands are politically sensitive but the
military situation takes precedence in the first hour.

I've prepared all documents for your review.
"""


@dataclass
class ParsedActionItem:
    """A parsed action item from agent response."""

    item_type: str  # approval, option, operation, demand, info
    title: str
    content: str
    urgency: str = "medium"
    classification: str = "confidential"

    # For approvals
    impacts: dict[str, int] = field(default_factory=dict)

    # For options
    options: list[dict[str, Any]] = field(default_factory=list)

    # For operations
    codename: str = ""
    category: str = "recon"
    duration_hours: int = 48
    expected_outcome: str = ""

    # For demands
    demands: list[dict[str, Any]] = field(default_factory=list)
    warning_text: str = ""


def extract_structured_items(response: str) -> tuple[str, list[ParsedActionItem]]:
    """Extract structured action items from agent response.

    Returns:
        Tuple of (narrative_text, list_of_action_items)
    """
    import re

    items: list[ParsedActionItem] = []

    # Split response into narrative and structured parts
    # Find the first structured block marker
    markers = [
        r'\[AUTHORIZATION REQUEST\]',
        r'\[OPTIONS\]',
        r'\[OPERATION PROPOSAL\]',
        r'\[DEMANDS\]',
        r'\[INFO\]',
    ]

    # Find where structured content begins
    first_marker_pos = len(response)
    for marker in markers:
        match = re.search(marker, response)
        if match and match.start() < first_marker_pos:
            first_marker_pos = match.start()

    narrative = response[:first_marker_pos].strip()
    structured_part = response[first_marker_pos:].strip()

    # Parse authorization requests
    auth_pattern = r'\[AUTHORIZATION REQUEST\]\s*Title:\s*(.+?)\s*Content:\s*(.+?)\s*Urgency:\s*(\w+)\s*Impacts:\s*(.+?)(?=\[|$)'
    for match in re.finditer(auth_pattern, structured_part, re.DOTALL | re.IGNORECASE):
        title, content, urgency, impacts_str = match.groups()
        impacts = _parse_impacts(impacts_str.strip())
        items.append(ParsedActionItem(
            item_type="approval",
            title=title.strip(),
            content=content.strip(),
            urgency=urgency.strip().lower(),
            impacts=impacts,
        ))

    # Parse options
    options_pattern = r'\[OPTIONS\]\s*Title:\s*(.+?)(?:\n)((?:\d+\..+?(?:\n|$))+)'
    for match in re.finditer(options_pattern, structured_part, re.DOTALL | re.IGNORECASE):
        title = match.group(1).strip()
        options_block = match.group(2)

        options = []
        opt_pattern = r'(\d+)\.\s*(.+?)\s*\|\s*Impacts:\s*(.+?)(?:\n|$)'
        for opt_match in re.finditer(opt_pattern, options_block, re.IGNORECASE):
            opt_num, opt_text, opt_impacts = opt_match.groups()
            options.append({
                "id": f"opt{opt_num}",
                "text": opt_text.strip(),
                "impacts": _parse_impacts(opt_impacts.strip()),
            })

        if options:
            items.append(ParsedActionItem(
                item_type="option",
                title=title,
                content=f"Select one of {len(options)} options",
                options=options,
            ))

    # Parse operation proposals
    op_pattern = r'\[OPERATION PROPOSAL\]\s*Codename:\s*(.+?)\s*Category:\s*(\w+)\s*Duration:\s*(\d+)\s*hours?\s*Description:\s*(.+?)\s*Expected Outcome:\s*(.+?)(?=\[|$)'
    for match in re.finditer(op_pattern, structured_part, re.DOTALL | re.IGNORECASE):
        codename, category, duration, description, outcome = match.groups()
        items.append(ParsedActionItem(
            item_type="operation",
            title=f"Operation {codename.strip()}",
            content=description.strip(),
            codename=codename.strip(),
            category=category.strip().lower(),
            duration_hours=int(duration),
            expected_outcome=outcome.strip(),
        ))

    # Parse demands
    demands_pattern = r'\[DEMANDS\]\s*Title:\s*(.+?)(?:\nWarning:\s*(.+?))?\s*(?:\n)((?:\d+\..+?(?:\n|$))+)'
    for match in re.finditer(demands_pattern, structured_part, re.DOTALL | re.IGNORECASE):
        title = match.group(1).strip()
        warning = (match.group(2) or "").strip()
        demands_block = match.group(3)

        demands = []
        demand_pattern = r'(\d+)\.\s*(.+?)\s*\|\s*Agree:\s*(.+?)\s*\|\s*Disagree:\s*(.+?)(?:\n|$)'
        for d_match in re.finditer(demand_pattern, demands_block, re.IGNORECASE):
            d_num, d_text, agree_impacts, disagree_impacts = d_match.groups()
            demands.append({
                "id": f"d{d_num}",
                "text": d_text.strip(),
                "agree_impacts": _parse_impacts(agree_impacts.strip()),
                "disagree_impacts": _parse_impacts(disagree_impacts.strip()),
            })

        if demands:
            items.append(ParsedActionItem(
                item_type="demand",
                title=title,
                content=f"{len(demands)} demands",
                demands=demands,
                warning_text=warning,
            ))

    # Parse info items
    info_pattern = r'\[INFO\]\s*Title:\s*(.+?)\s*Classification:\s*(\w+)\s*Content:\s*(.+?)(?=\[|$)'
    for match in re.finditer(info_pattern, structured_part, re.DOTALL | re.IGNORECASE):
        title, classification, content = match.groups()
        items.append(ParsedActionItem(
            item_type="info",
            title=title.strip(),
            content=content.strip(),
            classification=classification.strip().lower(),
        ))

    return narrative, items


def _parse_impacts(impacts_str: str) -> dict[str, int]:
    """Parse impacts string like 'military_readiness:+25, coalition:-10'."""
    import re

    impacts = {}
    # Match patterns like "metric:+25" or "metric:-10" or "metric:25"
    pattern = r'(\w+):\s*([+-]?\d+)'
    for match in re.finditer(pattern, impacts_str):
        metric, value = match.groups()
        impacts[metric] = int(value)
    return impacts


def convert_to_action_items(
    parsed_items: list[ParsedActionItem],
    agent_name: str,
    agent_role: str,
) -> list:
    """Convert ParsedActionItems to ActionItem objects.

    This bridges the new structured parsing with existing ActionItem system.
    """
    from pm6.core.action_items import (
        create_approval_request,
        create_demand_item,
        create_info_item,
        create_operation_proposal,
        create_option_item,
        OperationCategory,
        UrgencyLevel,
        ClassificationLevel,
    )

    action_items = []

    for parsed in parsed_items:
        if parsed.item_type == "approval":
            urgency = UrgencyLevel(parsed.urgency) if parsed.urgency in [u.value for u in UrgencyLevel] else UrgencyLevel.MEDIUM
            item = create_approval_request(
                agent_name,
                agent_role,
                parsed.title,
                parsed.content,
                parsed.impacts,
                urgency,
            )
            action_items.append(item)

        elif parsed.item_type == "option":
            options = []
            for opt in parsed.options:
                options.append({
                    "text": opt["text"],
                    "impacts": opt.get("impacts", {}),
                })
            item = create_option_item(
                agent_name,
                agent_role,
                parsed.title,
                parsed.content,
                options,
            )
            action_items.append(item)

        elif parsed.item_type == "operation":
            category_map = {
                "cyber": OperationCategory.CYBER,
                "kinetic": OperationCategory.KINETIC,
                "humint": OperationCategory.HUMINT,
                "sigint": OperationCategory.SIGINT,
                "recon": OperationCategory.RECON,
                "rescue": OperationCategory.RESCUE,
                "diplomatic": OperationCategory.DIPLOMATIC,
            }
            category = category_map.get(parsed.category, OperationCategory.RECON)

            item = create_operation_proposal(
                agent_name,
                agent_role,
                parsed.codename,
                category,
                parsed.content,
                parsed.duration_hours,
                parsed.expected_outcome,
            )
            action_items.append(item)

        elif parsed.item_type == "demand":
            demands = []
            for d in parsed.demands:
                demands.append({
                    "text": d["text"],
                    "agree_impacts": d.get("agree_impacts", {}),
                    "disagree_impacts": d.get("disagree_impacts", {}),
                })
            item = create_demand_item(
                agent_name,
                agent_role,
                parsed.title,
                demands,
                parsed.warning_text,
            )
            action_items.append(item)

        elif parsed.item_type == "info":
            item = create_info_item(
                agent_name,
                agent_role,
                parsed.content,
                parsed.title,
            )
            action_items.append(item)

    return action_items
