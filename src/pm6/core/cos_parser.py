"""Chief of Staff Parsing Pipeline.

Parses natural language agent responses into structured ActionItems.
Uses LLM to extract and classify content into actionable items.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from pm6.core.action_items import (
    ActionItem,
    ActionItemType,
    ClassificationLevel,
    DemandItem,
    ImpactPreview,
    OperationCategory,
    OptionItem,
    UrgencyLevel,
    create_approval_request,
    create_demand_item,
    create_info_item,
    create_metric_update,
    create_operation_proposal,
    create_option_item,
)

if TYPE_CHECKING:
    from pm6.llm import LLMClient

logger = logging.getLogger("pm6.core.cos_parser")


# Parsing prompt template
PARSING_PROMPT = """You are the Chief of Staff parsing an agent's response to extract structured action items for the Prime Minister.

Agent: {agent_name}
Role: {agent_role}

Response to parse:
---
{agent_response}
---

Extract ALL actionable items from this response. Classify each into ONE of these types:

1. INFO - Pure status updates, situational awareness (no action needed)
2. METRIC_UPDATE - Specific numbers that should update world state (e.g., "240 hostages confirmed")
3. APPROVAL - Authorization requests requiring PM decision (e.g., "recommend immediate deployment")
4. DEMAND - Stakeholder demands the PM should respond to (e.g., "we demand immediate negotiation")
5. OPTION - Multiple choices where PM must pick one (e.g., "Option 1: X, Option 2: Y")
6. OPERATION - Time-bound operations with specific duration (e.g., "48-72 hour infiltration")

For each item, extract:
- title: Short descriptive title
- content: Full description
- urgency: critical/high/medium/low
- impacts: Predicted effects on metrics (military_readiness, coalition_stability, etc.)

For OPERATION items, also extract:
- codename: Operation name if given
- category: cyber/kinetic/humint/sigint/recon/rescue/diplomatic
- duration_hours: Estimated duration in hours
- expected_outcome: What success looks like

For DEMAND items, extract multiple demands with agree/disagree impacts.

For OPTION items, extract each option with its individual impacts.

Output ONLY valid JSON in this exact format:
{{
  "items": [
    {{
      "type": "approval",
      "title": "Reserve Mobilization",
      "content": "Request authorization for 300,000 reserve callup to reach full operational capacity",
      "urgency": "high",
      "impacts": {{"military_readiness": 25, "coalition_stability": 10, "international_pressure": 5}}
    }},
    {{
      "type": "operation",
      "title": "Communication Infiltration",
      "codename": "SILENT FREQUENCY",
      "category": "cyber",
      "content": "Exploit cellular tower vulnerabilities in northern Gaza",
      "duration_hours": 72,
      "expected_outcome": "Hamas military communication intercept capability",
      "urgency": "medium"
    }},
    {{
      "type": "demand",
      "title": "Hostage Families Demands",
      "demands": [
        {{
          "text": "Negotiate immediately with Hamas",
          "agree_impacts": {{"families_relations": 20, "coalition_stability": -10}},
          "disagree_impacts": {{"families_relations": -15}}
        }}
      ],
      "warning_text": "Mass demonstration planned tomorrow",
      "urgency": "critical"
    }},
    {{
      "type": "info",
      "title": "Operational Status",
      "content": "Ground forces positioned for multi-axis assault",
      "urgency": "low"
    }}
  ]
}}

Important:
- Extract EVERY actionable item, don't miss any
- Be specific with impact values (use integers)
- If duration is given as range (48-72h), use the midpoint
- Distinguish between "recommend" (APPROVAL) and "option" (OPTION)
- METRIC_UPDATE is for confirmed facts that update state, not proposals"""


class CosParser:
    """Parses agent responses into structured action items."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize parser.

        Args:
            llm_client: LLM client for parsing. If None, uses rule-based fallback.
        """
        self._llm = llm_client
        self._cache: dict[str, list[ActionItem]] = {}

    def parse_response(
        self,
        agent_name: str,
        agent_role: str,
        response: str,
        use_llm: bool = True,
    ) -> list[ActionItem]:
        """Parse an agent response into action items.

        Args:
            agent_name: Name of the responding agent.
            agent_role: Role of the responding agent.
            response: The agent's response text.
            use_llm: Whether to use LLM parsing (vs rule-based).

        Returns:
            List of ActionItem objects extracted from response.
        """
        if not response or not response.strip():
            return []

        # Check cache
        cache_key = f"{agent_name}:{hash(response)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Parse
        if use_llm and self._llm:
            items = self._parse_with_llm(agent_name, agent_role, response)
        else:
            items = self._parse_with_rules(agent_name, agent_role, response)

        # Cache results
        self._cache[cache_key] = items
        return items

    def _parse_with_llm(
        self,
        agent_name: str,
        agent_role: str,
        response: str,
    ) -> list[ActionItem]:
        """Parse response using LLM.

        Args:
            agent_name: Agent name.
            agent_role: Agent role.
            response: Response text.

        Returns:
            List of parsed ActionItems.
        """
        prompt = PARSING_PROMPT.format(
            agent_name=agent_name,
            agent_role=agent_role,
            agent_response=response,
        )

        try:
            # Call LLM
            llm_response = self._llm.complete(
                prompt,
                system="You are a JSON extraction assistant. Output only valid JSON.",
                max_tokens=2000,
            )

            # Extract JSON from response
            json_str = self._extract_json(llm_response)
            data = json.loads(json_str)

            # Convert to ActionItems
            items = []
            for item_data in data.get("items", []):
                item = self._data_to_action_item(item_data, agent_name, agent_role)
                if item:
                    items.append(item)

            logger.info(f"LLM parsed {len(items)} items from {agent_name}")
            return items

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._parse_with_rules(agent_name, agent_role, response)
        except Exception as e:
            logger.error(f"LLM parsing error: {e}")
            return self._parse_with_rules(agent_name, agent_role, response)

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text that might have extra content."""
        # Try to find JSON object
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0)
        return text

    def _data_to_action_item(
        self,
        data: dict[str, Any],
        agent_name: str,
        agent_role: str,
    ) -> ActionItem | None:
        """Convert parsed data dict to ActionItem."""
        item_type = data.get("type", "info").lower()
        title = data.get("title", "")
        content = data.get("content", "")
        urgency = UrgencyLevel(data.get("urgency", "medium"))

        try:
            if item_type == "info":
                return create_info_item(agent_name, agent_role, content, title)

            elif item_type == "metric_update":
                return create_metric_update(
                    agent_name,
                    agent_role,
                    data.get("metric_key", ""),
                    data.get("metric_value"),
                    content=content,
                )

            elif item_type == "approval":
                return create_approval_request(
                    agent_name,
                    agent_role,
                    title,
                    content,
                    data.get("impacts", {}),
                    urgency,
                )

            elif item_type == "demand":
                demands = []
                for d in data.get("demands", []):
                    demands.append({
                        "text": d.get("text", ""),
                        "agree_impacts": d.get("agree_impacts", {}),
                        "disagree_impacts": d.get("disagree_impacts", {}),
                    })
                return create_demand_item(
                    agent_name,
                    agent_role,
                    title,
                    demands,
                    data.get("warning_text", ""),
                )

            elif item_type == "option":
                options = []
                for o in data.get("options", []):
                    options.append({
                        "text": o.get("text", ""),
                        "description": o.get("description", ""),
                        "risk_level": o.get("risk_level", "medium"),
                        "impacts": o.get("impacts", {}),
                    })
                return create_option_item(
                    agent_name,
                    agent_role,
                    title,
                    content,
                    options,
                )

            elif item_type == "operation":
                category_str = data.get("category", "recon").lower()
                try:
                    category = OperationCategory(category_str)
                except ValueError:
                    category = OperationCategory.RECON

                return create_operation_proposal(
                    agent_name,
                    agent_role,
                    data.get("codename", title.upper().replace(" ", "_")),
                    category,
                    content,
                    data.get("duration_hours", 48),
                    data.get("expected_outcome", ""),
                )

            else:
                logger.warning(f"Unknown item type: {item_type}")
                return create_info_item(agent_name, agent_role, content, title)

        except Exception as e:
            logger.error(f"Error creating action item: {e}")
            return None

    def _parse_with_rules(
        self,
        agent_name: str,
        agent_role: str,
        response: str,
    ) -> list[ActionItem]:
        """Parse response using rule-based extraction (fallback).

        Uses keyword matching and pattern recognition.
        Less accurate than LLM but works without API calls.
        """
        items: list[ActionItem] = []

        # Split into sentences/paragraphs for analysis
        lines = [l.strip() for l in response.split('\n') if l.strip()]

        # Patterns for different item types
        approval_patterns = [
            r'(?:recommend|request|authorize|approval|deploy|mobilize|callup)',
            r'(?:immediate|urgent|authorization|permission)',
        ]
        operation_patterns = [
            r'(?:operation|op\s+\w+|infiltration|mission)',
            r'(?:\d+[-–]\d+\s*(?:hours?|h)|within\s+\d+)',
        ]
        demand_patterns = [
            r'(?:demand|insist|require|must|need\s+to)',
            r'(?:we\s+(?:want|need|demand)|families)',
        ]
        option_patterns = [
            r'(?:option\s*[1-9]|alternative|choice)',
            r'(?:either|or\s+we\s+can)',
        ]
        metric_patterns = [
            r'(\d+)\s*(?:hostages?|casualties|percent|%)',
            r'(?:confirmed|verified|current)\s*:?\s*(\d+)',
        ]

        current_section = ""
        collected_content = []

        for line in lines:
            line_lower = line.lower()

            # Check for operation proposals
            if any(re.search(p, line_lower) for p in operation_patterns):
                # Extract duration if present
                duration_match = re.search(r'(\d+)[-–]?(\d+)?\s*(?:hours?|h)', line_lower)
                duration = 48  # default
                if duration_match:
                    d1 = int(duration_match.group(1))
                    d2 = int(duration_match.group(2)) if duration_match.group(2) else d1
                    duration = (d1 + d2) // 2

                # Extract codename if present
                codename_match = re.search(r'(?:operation|op)\s+([A-Z][A-Z\s]+)', line, re.IGNORECASE)
                codename = codename_match.group(1).strip() if codename_match else "UNNAMED"

                items.append(create_operation_proposal(
                    agent_name,
                    agent_role,
                    codename.upper().replace(" ", "_"),
                    OperationCategory.RECON,
                    line,
                    duration,
                    "Operation outcome pending",
                ))

            # Check for approval requests
            elif any(re.search(p, line_lower) for p in approval_patterns):
                items.append(create_approval_request(
                    agent_name,
                    agent_role,
                    self._extract_title(line),
                    line,
                    {"impact": 10},  # Default impact
                    UrgencyLevel.MEDIUM,
                ))

            # Check for demands
            elif any(re.search(p, line_lower) for p in demand_patterns):
                items.append(create_demand_item(
                    agent_name,
                    agent_role,
                    "Stakeholder Demand",
                    [{"text": line, "agree_impacts": {}, "disagree_impacts": {}}],
                ))

            # Check for metric updates
            elif metric_match := re.search(r'(\d+)\s*(hostages?|casualties)', line_lower):
                value = int(metric_match.group(1))
                metric = "hostage_count" if "hostage" in metric_match.group(2) else "casualties"
                items.append(create_metric_update(
                    agent_name,
                    agent_role,
                    metric,
                    value,
                    content=line,
                ))

            # Default to info item for substantial content
            elif len(line) > 50:
                items.append(create_info_item(
                    agent_name,
                    agent_role,
                    line,
                    "Status Update",
                ))

        # Deduplicate similar items
        items = self._deduplicate_items(items)

        logger.info(f"Rule-based parsed {len(items)} items from {agent_name}")
        return items

    def _extract_title(self, text: str) -> str:
        """Extract a short title from text."""
        # Take first few words
        words = text.split()[:6]
        title = " ".join(words)
        if len(title) > 50:
            title = title[:47] + "..."
        return title

    def _deduplicate_items(self, items: list[ActionItem]) -> list[ActionItem]:
        """Remove duplicate or very similar items."""
        seen_content: set[str] = set()
        unique_items: list[ActionItem] = []

        for item in items:
            # Create a content fingerprint
            fingerprint = f"{item.type.value}:{item.content[:100]}"
            if fingerprint not in seen_content:
                seen_content.add(fingerprint)
                unique_items.append(item)

        return unique_items

    def clear_cache(self) -> None:
        """Clear the parsing cache."""
        self._cache.clear()


class ActionItemsManager:
    """Manages action items for a CoS session.

    Stores pending items, handles resolutions, applies impacts.
    """

    def __init__(self) -> None:
        """Initialize manager."""
        self._pending: dict[str, ActionItem] = {}
        self._resolved: list[ActionItem] = []
        self._applied_metrics: list[ActionItem] = []

    @property
    def pending_items(self) -> list[ActionItem]:
        """Get all pending action items."""
        return list(self._pending.values())

    @property
    def pending_count(self) -> int:
        """Get count of pending items."""
        return len(self._pending)

    @property
    def pending_by_type(self) -> dict[ActionItemType, list[ActionItem]]:
        """Get pending items grouped by type."""
        result: dict[ActionItemType, list[ActionItem]] = {}
        for item in self._pending.values():
            if item.type not in result:
                result[item.type] = []
            result[item.type].append(item)
        return result

    def add_item(self, item: ActionItem) -> None:
        """Add an action item.

        Args:
            item: The action item to add.
        """
        if item.type == ActionItemType.METRIC_UPDATE:
            # Metric updates are auto-applied, don't add to pending
            self._applied_metrics.append(item)
        elif item.type == ActionItemType.INFO:
            # Info items don't need action, but we track them
            self._resolved.append(item)
        else:
            # Other types need player action
            self._pending[item.id] = item

    def add_items(self, items: list[ActionItem]) -> None:
        """Add multiple action items."""
        for item in items:
            self.add_item(item)

    def get_item(self, item_id: str) -> ActionItem | None:
        """Get a pending item by ID."""
        return self._pending.get(item_id)

    def resolve_item(
        self,
        item_id: str,
        status: ActionItemStatus,
    ) -> ActionItem | None:
        """Resolve a pending item.

        Args:
            item_id: ID of item to resolve.
            status: Resolution status.

        Returns:
            The resolved item or None if not found.
        """
        if item_id not in self._pending:
            return None

        item = self._pending.pop(item_id)
        item.resolve(status)
        self._resolved.append(item)
        return item

    def get_impacts_for_approval(
        self,
        item_id: str,
        approved: bool,
    ) -> dict[str, int | float]:
        """Get impacts to apply for an approval decision.

        Args:
            item_id: ID of approval item.
            approved: Whether approved or denied.

        Returns:
            Dict of metric changes to apply.
        """
        item = self._pending.get(item_id)
        if not item or item.type != ActionItemType.APPROVAL:
            return {}

        if approved:
            return {i.metric: i.change for i in item.impacts}
        else:
            # Denial typically has no direct impact (or could have negative relationship impact)
            return {}

    def get_impacts_for_demands(
        self,
        item_id: str,
        responses: dict[str, bool],  # demand_id -> agreed
    ) -> dict[str, int | float]:
        """Get impacts for demand responses.

        Args:
            item_id: ID of demand item.
            responses: Dict mapping demand_id to agreed (True) or disagreed (False).

        Returns:
            Combined dict of metric changes.
        """
        item = self._pending.get(item_id)
        if not item or item.type != ActionItemType.DEMAND:
            return {}

        combined: dict[str, int | float] = {}
        for demand in item.demands:
            if demand.id in responses:
                agreed = responses[demand.id]
                impacts = demand.agree_impacts if agreed else demand.disagree_impacts
                for impact in impacts:
                    combined[impact.metric] = combined.get(impact.metric, 0) + impact.change
                demand.response = "agreed" if agreed else "disagreed"

        return combined

    def get_impacts_for_option(
        self,
        item_id: str,
        option_id: str,
    ) -> dict[str, int | float]:
        """Get impacts for selecting an option.

        Args:
            item_id: ID of option item.
            option_id: ID of selected option.

        Returns:
            Dict of metric changes.
        """
        item = self._pending.get(item_id)
        if not item or item.type != ActionItemType.OPTION:
            return {}

        for option in item.options:
            if option.id == option_id:
                return {i.metric: i.change for i in option.impacts}

        return {}

    def get_metric_updates(self) -> dict[str, Any]:
        """Get all metric updates that should be applied.

        Returns:
            Dict of metric_key -> new_value.
        """
        updates = {}
        for item in self._applied_metrics:
            if item.metric_key:
                updates[item.metric_key] = item.metric_value
        return updates

    def has_mandatory_pending(self) -> bool:
        """Check if there are mandatory items that must be resolved.

        Returns:
            True if there are high-urgency items pending.
        """
        for item in self._pending.values():
            if item.urgency in (UrgencyLevel.CRITICAL, UrgencyLevel.HIGH):
                return True
        return False

    def reset(self) -> None:
        """Reset all items (new turn)."""
        self._pending.clear()
        self._resolved.clear()
        self._applied_metrics.clear()

    def toDict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pending": [item.toDict() for item in self._pending.values()],
            "resolved": [item.toDict() for item in self._resolved],
            "applied_metrics": [item.toDict() for item in self._applied_metrics],
        }
