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
    ActionItemStatus,
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
        Optimized for crisis simulation agent response patterns.
        """
        items: list[ActionItem] = []
        response_lower = response.lower()

        # First pass: Look for RECOMMENDATIONS with numbered items (OPTIONS)
        # Pattern: "RECOMMENDATIONS:" followed by numbered items
        if re.search(r'recommendations?\s*:', response_lower):
            option_items = self._extract_numbered_options(response, agent_name, agent_role)
            if option_items:
                items.extend(option_items)

        # Second pass: Look for DEMANDS (may or may not have numbered items)
        # Pattern: "We demand" or emotional appeal language
        if re.search(r'we\s+demand|demand\s+you|demands?\s+immediate', response_lower):
            demand_items = self._extract_demands(response, agent_name, agent_role)
            if demand_items:
                items.extend(demand_items)

        # Third pass: Look for AUTHORIZATION patterns
        # Matches: "AUTHORIZATION REQUESTED", "AUTHORIZATION REQUESTS:", "awaiting authorization"
        auth_patterns = [
            r'authorization\s+request(?:ed|s)?[:\s]*([^.\n]*)',
            r'await(?:ing)?\s+(?:government\s+)?authorization\s+(?:to\s+)?([^.\n]*)',
            r'request(?:ing|s)?\s+authorization\s+(?:for|to)\s+([^.\n]*)',
        ]
        for auth_pattern in auth_patterns:
            auth_match = re.search(auth_pattern, response, re.IGNORECASE)
            if auth_match:
                auth_context = auth_match.group(1).strip() if auth_match.group(1) else auth_match.group(0).strip()
                items.append(create_approval_request(
                    agent_name,
                    agent_role,
                    f"Authorization Request from {agent_role}",
                    auth_context or "Awaiting your authorization to proceed",
                    self._estimate_impacts(auth_context or response[:200], agent_role),
                    UrgencyLevel.CRITICAL,
                ))
                break  # Only create one approval per response

        # Third pass: Look for OPERATION proposals
        # Pattern: "Operation [NAME]" or "48-72 hour" duration mentions
        op_match = re.search(
            r'(?:operation|op)\s+([A-Z][A-Z\s_]+)|(\d+)[-–](\d+)\s*(?:hours?|h)\s+(?:operation|mission|infiltration)',
            response,
            re.IGNORECASE
        )
        if op_match:
            codename = op_match.group(1) or "TACTICAL_OP"
            # Extract duration
            duration_match = re.search(r'(\d+)[-–](\d+)\s*(?:hours?|h)', response_lower)
            duration = 48
            if duration_match:
                d1, d2 = int(duration_match.group(1)), int(duration_match.group(2))
                duration = (d1 + d2) // 2

            # Find operation description
            op_context = self._extract_operation_context(response)
            items.append(create_operation_proposal(
                agent_name,
                agent_role,
                codename.strip().upper().replace(" ", "_"),
                self._guess_operation_category(response_lower, agent_role),
                op_context,
                duration,
                "Objective completion pending assessment",
            ))

        # Fourth pass: Look for metric updates (concrete numbers)
        # Pattern: "X hostages", "X casualties", "X% ready"
        metric_patterns = [
            (r'(\d+)\s*hostages?', 'hostage_count'),
            (r'(\d+)\s*(?:civilian\s+)?casualties', 'civilian_casualties'),
            (r'(\d+)\s*(?:soldiers?|troops?)\s+(?:killed|casualties)', 'military_casualties'),
            (r'(\d+)[%\s]+(?:readiness|ready|mobilized)', 'military_readiness'),
        ]
        for pattern, metric_key in metric_patterns:
            match = re.search(pattern, response_lower)
            if match:
                value = int(match.group(1))
                context_line = self._extract_context_line(response, match.start())
                items.append(create_metric_update(
                    agent_name,
                    agent_role,
                    metric_key,
                    value,
                    content=context_line,
                ))

        # Fifth pass: If no structured items found, create INFO item for substantive responses
        if not items and len(response) > 100:
            # Create a summary info item
            summary = response[:300] + "..." if len(response) > 300 else response
            items.append(create_info_item(
                agent_name,
                agent_role,
                summary,
                f"Briefing from {agent_role}",
            ))

        # Deduplicate
        items = self._deduplicate_items(items)

        logger.info(f"Rule-based parsed {len(items)} items from {agent_name}")
        return items

    def _extract_numbered_options(
        self,
        response: str,
        agent_name: str,
        agent_role: str,
    ) -> list[ActionItem]:
        """Extract numbered recommendations as OPTIONS.

        Pattern: "IMMEDIATE RECOMMENDATIONS:" followed by numbered items
        Creates an OPTION card where player picks one.
        """
        # First, strip markdown formatting for cleaner extraction
        clean_response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)  # **bold** -> bold
        clean_response = re.sub(r'\*([^*]+)\*', r'\1', clean_response)  # *italic* -> italic

        # Find numbered items: "1. ...", "2. ...", "1) ...", etc.
        # Capture everything after the number until end of line
        numbered_matches = re.findall(
            r'(?:^|\n)\s*(\d+)[.)]\s*(.+?)(?=\n\s*\d+[.)]|\n\n|\n[A-Z]|\Z)',
            clean_response,
            re.MULTILINE | re.DOTALL
        )

        if not numbered_matches or len(numbered_matches) < 2:
            return []

        # Build options
        options = []
        for num, text in numbered_matches:
            # Clean up the text
            text = text.strip()
            # Take first line if multi-line
            text = text.split('\n')[0].strip()
            if len(text) > 10:  # Filter out noise
                options.append({
                    "text": text,
                    "description": "",
                    "risk_level": "medium",
                    "impacts": self._estimate_impacts(text, agent_role),
                })

        if options:
            return [create_option_item(
                agent_name,
                agent_role,
                f"Recommendations from {agent_role}",
                "Select one of the following recommended actions:",
                options,
            )]

        return []

    def _extract_demands(
        self,
        response: str,
        agent_name: str,
        agent_role: str,
    ) -> list[ActionItem]:
        """Extract demands from response.

        Handles both numbered demands and paragraph-style demands.
        """
        # Strip markdown formatting for cleaner extraction
        clean_response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)
        clean_response = re.sub(r'\*([^*]+)\*', r'\1', clean_response)

        # First try numbered demands
        numbered_matches = re.findall(
            r'(?:^|\n)\s*(\d+)[.)]\s*(.+?)(?=\n\s*\d+[.)]|\n\n|\n[A-Z]|\Z)',
            clean_response,
            re.MULTILINE | re.DOTALL
        )

        demands = []

        # Check for numbered format
        if numbered_matches and len(numbered_matches) >= 2:
            for num, text in numbered_matches:
                text = text.strip().split('\n')[0].strip()
                if len(text) > 10:
                    demands.append({
                        "text": text,
                        "agree_impacts": self._estimate_demand_impacts(text, True),
                        "disagree_impacts": self._estimate_demand_impacts(text, False),
                    })
        else:
            # Extract key demand phrases from paragraph
            demand_phrases = []

            # Look for "We demand [action]" pattern
            demand_match = re.search(
                r'we\s+demand\s+(?:you\s+)?(.+?)(?:\.|!|$)',
                response,
                re.IGNORECASE
            )
            if demand_match:
                demand_phrases.append(demand_match.group(1).strip())

            # Look for imperative sentences
            imperative_patterns = [
                r'(?:launch|start|begin)\s+(.+?)(?:immediately|now|today)',
                r'(?:mobilize|deploy)\s+(.+?)(?:\.|!)',
                r'pay\s+whatever\s+price',
                r'use\s+every\s+(.+?)(?:\.|!)',
            ]
            for pattern in imperative_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    phrase = match.group(0).strip()
                    if phrase and phrase not in [d.get("text", "") for d in demands]:
                        demand_phrases.append(phrase)

            # Create demands from phrases (max 3)
            for phrase in demand_phrases[:3]:
                if len(phrase) > 10:
                    demands.append({
                        "text": phrase,
                        "agree_impacts": self._estimate_demand_impacts(phrase, True),
                        "disagree_impacts": self._estimate_demand_impacts(phrase, False),
                    })

        if demands:
            # Find warning text
            warning_match = re.search(
                r'(?:will\s+not|cannot|won\'t|not\s+accept|watching|clock\s+is\s+ticking)',
                response,
                re.IGNORECASE
            )
            warning = ""
            if warning_match:
                warning = self._extract_context_line(response, warning_match.start())

            return [create_demand_item(
                agent_name,
                agent_role,
                f"Demands from {agent_role}",
                demands,
                warning,
            )]

        return []

    def _estimate_impacts(self, text: str, agent_role: str) -> dict[str, int]:
        """Estimate impacts based on text content and agent role."""
        impacts = {}
        text_lower = text.lower()

        # Military-related
        if re.search(r'mobiliz|deploy|troops|reserve|military', text_lower):
            impacts['military_readiness'] = 15
        if re.search(r'strike|attack|offensive|assault', text_lower):
            impacts['international_pressure'] = 10

        # Coalition/political
        if re.search(r'coalition|cabinet|minister', text_lower):
            impacts['coalition_stability'] = 10

        # Hostage-related
        if re.search(r'hostage|rescue|negoti', text_lower):
            impacts['hostage_risk'] = -5

        # Role-based defaults
        if 'idf' in agent_role.lower() or 'military' in agent_role.lower():
            impacts.setdefault('military_readiness', 10)
        elif 'hostage' in agent_role.lower() or 'families' in agent_role.lower():
            impacts.setdefault('public_morale', -5)
        elif 'mossad' in agent_role.lower() or 'intelligence' in agent_role.lower():
            impacts.setdefault('intelligence_quality', 10)

        return impacts or {"general_impact": 10}

    def _estimate_demand_impacts(self, text: str, agreed: bool) -> dict[str, int]:
        """Estimate impacts for agreeing/disagreeing with a demand."""
        text_lower = text.lower()
        multiplier = 1 if agreed else -1

        if re.search(r'negotiat|talks|dialog', text_lower):
            return {"diplomatic_progress": 15 * multiplier, "military_momentum": -10 * multiplier}
        if re.search(r'rescue|extract|save', text_lower):
            return {"hostage_risk": -10 * multiplier, "military_risk": 5 * multiplier}
        if re.search(r'deploy|attack|strike', text_lower):
            return {"military_readiness": 10 * multiplier, "international_pressure": 5 * multiplier}

        return {"stakeholder_relations": 10 * multiplier}

    def _guess_operation_category(self, text: str, agent_role: str) -> OperationCategory:
        """Guess operation category from text and agent role."""
        if re.search(r'cyber|hack|network|digital', text):
            return OperationCategory.CYBER
        if re.search(r'strike|bomb|missile|kinetic', text):
            return OperationCategory.KINETIC
        if re.search(r'asset|agent|source|humint', text):
            return OperationCategory.HUMINT
        if re.search(r'intercept|signal|comm|sigint', text):
            return OperationCategory.SIGINT
        if re.search(r'rescue|extract|hostage', text):
            return OperationCategory.RESCUE
        if re.search(r'recon|surveillance|observe', text):
            return OperationCategory.RECON

        # Agent role fallback
        if 'mossad' in agent_role.lower():
            return OperationCategory.HUMINT
        if 'idf' in agent_role.lower() or 'military' in agent_role.lower():
            return OperationCategory.KINETIC

        return OperationCategory.RECON

    def _extract_operation_context(self, response: str) -> str:
        """Extract operation description from response."""
        # Look for lines with operation context
        lines = response.split('\n')
        for line in lines:
            if re.search(r'operation|mission|objective|target', line, re.IGNORECASE):
                return line.strip()
        # Fallback: first substantial line
        for line in lines:
            if len(line.strip()) > 50:
                return line.strip()[:200]
        return "Operation details pending"

    def _extract_context_line(self, response: str, position: int) -> str:
        """Extract the line containing a match position."""
        # Find line boundaries
        start = response.rfind('\n', 0, position) + 1
        end = response.find('\n', position)
        if end == -1:
            end = len(response)
        return response[start:end].strip()

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

    def get_pending_items(self) -> list[ActionItem]:
        """Get all pending action items (alias for pending_items property)."""
        return list(self._pending.values())

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
        responses: dict[str, str | bool],  # demand_id -> 'agree'/'disagree' or True/False
    ) -> dict[str, int | float]:
        """Get impacts for demand responses.

        Args:
            item_id: ID of demand item.
            responses: Dict mapping demand_id to 'agree'/'disagree' (or True/False for agreed).

        Returns:
            Combined dict of metric changes.
        """
        item = self._pending.get(item_id)
        if not item or item.type != ActionItemType.DEMAND:
            return {}

        combined: dict[str, int | float] = {}
        for demand in item.demands:
            if demand.id in responses:
                response = responses[demand.id]
                # Handle both string ('agree'/'disagree') and boolean formats
                if isinstance(response, str):
                    agreed = response.lower() == 'agree'
                else:
                    agreed = bool(response)

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
