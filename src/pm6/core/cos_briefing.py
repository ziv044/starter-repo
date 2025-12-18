"""Chief of Staff Briefing Generator.

Aggregates agent outputs into a cohesive PM briefing with:
- Opening narrative
- Advisor position summaries
- Conflict detection
- Priority queue
- Recommendations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pm6.core.action_items import ActionItem, ActionItemType, UrgencyLevel

if TYPE_CHECKING:
    from pm6.llm import LLMClient

logger = logging.getLogger("pm6.core.cos_briefing")


@dataclass
class AdvisorPosition:
    """Summary of an advisor's position this turn."""

    agent_name: str
    agent_role: str
    summary: str
    faction: str = "friendly"  # friendly, ally, enemy
    urgency: str = "medium"
    action_items: list[ActionItem] = field(default_factory=list)


@dataclass
class ConflictDetected:
    """A detected conflict between advisors."""

    agent_a: str
    agent_b: str
    issue: str
    description: str


@dataclass
class PriorityItem:
    """An item in the priority queue."""

    urgency: str  # critical, high, medium, low
    item_type: str  # approval, demand, operation, etc.
    source: str  # agent role
    summary: str
    item_id: str


@dataclass
class CosBriefing:
    """Complete Chief of Staff briefing for a turn."""

    turn_number: int
    game_time: str
    hours_elapsed: int

    opening_narrative: str
    advisor_positions: list[AdvisorPosition]
    conflicts: list[ConflictDetected]
    priority_queue: list[PriorityItem]
    recommendation: str
    closing_narrative: str

    # All action items (for document rendering)
    action_items: list[ActionItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "turnNumber": self.turn_number,
            "gameTime": self.game_time,
            "hoursElapsed": self.hours_elapsed,
            "chiefOfStaffNarrative": self.opening_narrative,
            "advisorPositions": [
                {
                    "agentName": pos.agent_name,
                    "agentRole": pos.agent_role,
                    "summary": pos.summary,
                    "faction": pos.faction,
                    "urgency": pos.urgency,
                }
                for pos in self.advisor_positions
            ],
            "agentBriefs": [
                {
                    "agentName": pos.agent_name,
                    "agentRole": pos.agent_role,
                    "summary": pos.summary,
                    "faction": pos.faction,
                }
                for pos in self.advisor_positions
            ],
            "conflicts": [
                {
                    "agentA": c.agent_a,
                    "agentB": c.agent_b,
                    "issue": c.issue,
                    "description": c.description,
                }
                for c in self.conflicts
            ],
            "priorityQueue": [
                {
                    "urgency": p.urgency,
                    "itemType": p.item_type,
                    "source": p.source,
                    "summary": p.summary,
                    "itemId": p.item_id,
                }
                for p in self.priority_queue
            ],
            "recommendation": self.recommendation,
            "closingNarrative": self.closing_narrative,
            "actionItems": [item.to_dict() for item in self.action_items],
        }


# Briefing generation prompt
COS_BRIEFING_PROMPT = """You are the Prime Minister's Chief of Staff preparing a briefing.

## CURRENT SITUATION
Turn: {turn_number}
Time: {game_time}
Hours Elapsed: {hours_elapsed}

## AGENT RESPONSES THIS TURN
{agent_responses}

## WORLD STATE
{world_state}

## YOUR TASK
Generate a Chief of Staff briefing with:

1. OPENING (2-3 sentences): Set the stage. What's the critical situation right now?

2. ADVISOR SUMMARIES: For each advisor who spoke, 1-2 sentences capturing their key point.

3. CONFLICTS: If any advisors disagree, describe the conflict.

4. PRIORITY: Which action items are most urgent?

5. RECOMMENDATION: What should the PM address first and why?

Output as JSON:
{{
  "opening_narrative": "...",
  "conflicts": [
    {{"agent_a": "IDF Chief", "agent_b": "US SecState", "issue": "Response scale", "description": "..."}}
  ],
  "recommendation": "Address X first because...",
  "closing_narrative": "I've prepared all documents for your review."
}}

Be concise but impactful. This is a crisis - communicate urgency.
"""


class CosBriefingGenerator:
    """Generates Chief of Staff briefings from agent outputs."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """Initialize generator.

        Args:
            llm_client: Optional LLM for enhanced narrative generation.
        """
        self._llm = llm_client

    def generate_briefing(
        self,
        turn_number: int,
        game_time: str,
        hours_elapsed: int,
        agent_outputs: list[dict[str, Any]],
        action_items: list[ActionItem],
        world_state: dict[str, Any],
    ) -> CosBriefing:
        """Generate a complete CoS briefing.

        Args:
            turn_number: Current turn number.
            game_time: In-game datetime string.
            hours_elapsed: Hours elapsed since crisis start.
            agent_outputs: List of agent output dicts with name, role, content.
            action_items: All ActionItems parsed from agent responses.
            world_state: Current world state dict.

        Returns:
            Complete CosBriefing object.
        """
        # Build advisor positions
        positions = self._extract_positions(agent_outputs, action_items)

        # Detect conflicts
        conflicts = self._detect_conflicts(positions, agent_outputs)

        # Build priority queue from action items
        priority_queue = self._build_priority_queue(action_items)

        # Generate narrative (LLM or template-based)
        if self._llm:
            narrative = self._generate_narrative_llm(
                turn_number, game_time, hours_elapsed,
                agent_outputs, world_state
            )
        else:
            narrative = self._generate_narrative_template(
                turn_number, positions, conflicts, priority_queue
            )

        return CosBriefing(
            turn_number=turn_number,
            game_time=game_time,
            hours_elapsed=hours_elapsed,
            opening_narrative=narrative["opening"],
            advisor_positions=positions,
            conflicts=conflicts,
            priority_queue=priority_queue,
            recommendation=narrative["recommendation"],
            closing_narrative=narrative["closing"],
            action_items=action_items,
        )

    def _extract_positions(
        self,
        agent_outputs: list[dict[str, Any]],
        action_items: list[ActionItem],
    ) -> list[AdvisorPosition]:
        """Extract advisor positions from agent outputs."""
        positions = []

        # Map action items to agents
        items_by_agent: dict[str, list[ActionItem]] = {}
        for item in action_items:
            if item.source_agent not in items_by_agent:
                items_by_agent[item.source_agent] = []
            items_by_agent[item.source_agent].append(item)

        for output in agent_outputs:
            agent_name = output.get("agentName", "")
            agent_role = output.get("agentRole", output.get("role", ""))
            content = output.get("content", "")

            # Determine faction
            faction = self._determine_faction(agent_name, agent_role)

            # Create summary (first 2 sentences or 200 chars)
            summary = self._create_summary(content)

            # Determine urgency from action items
            agent_items = items_by_agent.get(agent_name, [])
            urgency = "medium"
            for item in agent_items:
                if item.urgency == UrgencyLevel.CRITICAL:
                    urgency = "critical"
                    break
                elif item.urgency == UrgencyLevel.HIGH:
                    urgency = "high"

            positions.append(AdvisorPosition(
                agent_name=agent_name,
                agent_role=agent_role,
                summary=summary,
                faction=faction,
                urgency=urgency,
                action_items=agent_items,
            ))

        return positions

    def _determine_faction(self, agent_name: str, agent_role: str) -> str:
        """Determine if agent is friendly, ally, or enemy."""
        name_lower = agent_name.lower()
        role_lower = agent_role.lower()

        # Enemy factions
        enemy_keywords = ["hamas", "hezbollah", "iran", "enemy", "hostile"]
        for keyword in enemy_keywords:
            if keyword in name_lower or keyword in role_lower:
                return "enemy"

        # Ally factions (external allies)
        ally_keywords = ["us_", "american", "secretary", "biden", "ally"]
        for keyword in ally_keywords:
            if keyword in name_lower or keyword in role_lower:
                return "ally"

        return "friendly"

    def _create_summary(self, content: str) -> str:
        """Create a 1-2 sentence summary from content."""
        if not content:
            return "No response provided."

        # Split into sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', content)

        # Take first 2 meaningful sentences (skip short ones)
        meaningful = [s for s in sentences if len(s) > 20]
        summary_sentences = meaningful[:2]

        if summary_sentences:
            summary = " ".join(summary_sentences)
        else:
            # Fallback: truncate
            summary = content[:200]
            if len(content) > 200:
                summary += "..."

        return summary

    def _detect_conflicts(
        self,
        positions: list[AdvisorPosition],
        agent_outputs: list[dict[str, Any]],
    ) -> list[ConflictDetected]:
        """Detect conflicts between advisor positions.

        Uses keyword analysis to find opposing viewpoints.
        """
        conflicts = []

        # Conflict patterns: (keyword_a, keyword_b, issue_description)
        conflict_patterns = [
            (["negotiate", "talks", "diplomatic", "ceasefire"],
             ["military", "strike", "force", "offensive", "destroy"],
             "Approach to conflict resolution"),
            (["hostages first", "families", "rescue priority"],
             ["military objectives", "strategic", "eliminate threat"],
             "Hostage vs military priorities"),
            (["restraint", "proportional", "international law"],
             ["maximum", "overwhelming", "decisive", "crush"],
             "Scale of military response"),
            (["coalition", "unity", "moderate"],
             ["far-right", "hardline", "no compromise"],
             "Coalition politics"),
        ]

        # Check each pair of positions
        for i, pos_a in enumerate(positions):
            for pos_b in positions[i + 1:]:
                # Skip if same faction type
                if pos_a.faction == "enemy" or pos_b.faction == "enemy":
                    continue

                # Get content for each
                content_a = pos_a.summary.lower()
                content_b = pos_b.summary.lower()

                # Check conflict patterns
                for keywords_a, keywords_b, issue in conflict_patterns:
                    a_has_first = any(kw in content_a for kw in keywords_a)
                    b_has_second = any(kw in content_b for kw in keywords_b)
                    a_has_second = any(kw in content_a for kw in keywords_b)
                    b_has_first = any(kw in content_b for kw in keywords_a)

                    if (a_has_first and b_has_second) or (a_has_second and b_has_first):
                        conflicts.append(ConflictDetected(
                            agent_a=pos_a.agent_role,
                            agent_b=pos_b.agent_role,
                            issue=issue,
                            description=f"{pos_a.agent_role} and {pos_b.agent_role} have conflicting positions on {issue.lower()}",
                        ))
                        break  # One conflict per pair

        return conflicts

    def _build_priority_queue(self, action_items: list[ActionItem]) -> list[PriorityItem]:
        """Build priority queue from action items."""
        priority_order = {
            UrgencyLevel.CRITICAL: 0,
            UrgencyLevel.HIGH: 1,
            UrgencyLevel.MEDIUM: 2,
            UrgencyLevel.LOW: 3,
            UrgencyLevel.ROUTINE: 4,
        }

        # Filter to actionable items only
        actionable_types = {
            ActionItemType.APPROVAL,
            ActionItemType.DEMAND,
            ActionItemType.OPTION,
            ActionItemType.OPERATION,
        }

        queue_items = []
        for item in action_items:
            if item.type in actionable_types:
                queue_items.append(PriorityItem(
                    urgency=item.urgency.value,
                    item_type=item.type.value,
                    source=item.source_role,
                    summary=item.title,
                    item_id=item.id,
                ))

        # Sort by urgency
        queue_items.sort(key=lambda x: priority_order.get(UrgencyLevel(x.urgency), 2))

        return queue_items

    def _generate_narrative_template(
        self,
        turn_number: int,
        positions: list[AdvisorPosition],
        conflicts: list[ConflictDetected],
        priority_queue: list[PriorityItem],
    ) -> dict[str, str]:
        """Generate narrative using templates (no LLM)."""
        # Opening based on turn
        if turn_number == 1:
            opening = (
                "Prime Minister, we are facing an unprecedented security crisis. "
                "Multiple breach points confirmed along the southern border. "
                "Your advisors have provided their initial assessments."
            )
        else:
            opening = (
                f"Prime Minister, turn {turn_number} briefing. "
                "The situation continues to develop. "
                "Here are your advisors' latest positions."
            )

        # Add conflict context
        if conflicts:
            conflict_text = " Note: " + conflicts[0].description + "."
            opening += conflict_text

        # Recommendation based on priority queue
        if priority_queue:
            top_item = priority_queue[0]
            recommendation = (
                f"I recommend addressing the {top_item.item_type} from {top_item.source} first. "
                f"This item is marked {top_item.urgency.upper()} priority."
            )
        else:
            recommendation = "Review the situation reports and prepare for the next turn."

        closing = "I've organized all documents by priority for your review."

        return {
            "opening": opening,
            "recommendation": recommendation,
            "closing": closing,
        }

    def _generate_narrative_llm(
        self,
        turn_number: int,
        game_time: str,
        hours_elapsed: int,
        agent_outputs: list[dict[str, Any]],
        world_state: dict[str, Any],
    ) -> dict[str, str]:
        """Generate narrative using LLM."""
        import json

        # Format agent responses
        agent_text = ""
        for output in agent_outputs:
            agent_text += f"\n### {output.get('agentRole', 'Agent')}\n"
            agent_text += output.get('content', '')[:500]
            agent_text += "\n---\n"

        prompt = COS_BRIEFING_PROMPT.format(
            turn_number=turn_number,
            game_time=game_time,
            hours_elapsed=hours_elapsed,
            agent_responses=agent_text,
            world_state=json.dumps(world_state, indent=2),
        )

        try:
            response = self._llm.complete(
                prompt,
                system="You are a Chief of Staff. Output JSON only.",
                max_tokens=1000,
            )

            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group(0))
                return {
                    "opening": data.get("opening_narrative", "Briefing in progress."),
                    "recommendation": data.get("recommendation", "Review all items."),
                    "closing": data.get("closing_narrative", "Documents ready for review."),
                }
        except Exception as e:
            logger.error(f"LLM narrative generation failed: {e}")

        # Fallback to template
        return self._generate_narrative_template(
            turn_number, [], [], []
        )


def create_briefing_from_turn_result(
    turn_result: dict[str, Any],
    world_state: dict[str, Any],
    action_items: list[ActionItem],
    llm_client: LLMClient | None = None,
) -> CosBriefing:
    """Create a CoS briefing from a pipeline turn result.

    Args:
        turn_result: The result from execute_turn().
        world_state: Current world state.
        action_items: Parsed action items.
        llm_client: Optional LLM client.

    Returns:
        CosBriefing object.
    """
    generator = CosBriefingGenerator(llm_client)

    # Extract agent outputs from turn result
    agent_outputs = []
    execute_agents_step = None
    for step in turn_result.get("steps", []):
        if step.get("stepName") == "execute_agents":
            execute_agents_step = step
            break

    if execute_agents_step:
        actions = execute_agents_step.get("outputs", {}).get("actions", [])
        for action in actions:
            agent_outputs.append({
                "agentName": action.get("agentName", ""),
                "agentRole": action.get("agentName", "").replace("_", " ").title(),
                "content": action.get("content", ""),
            })

    # Get turn info
    turn_number = turn_result.get("turnNumber", 1)
    game_time = world_state.get("turn_date", "Unknown")
    hours_elapsed = turn_result.get("hoursElapsed", 0)

    return generator.generate_briefing(
        turn_number=turn_number,
        game_time=game_time,
        hours_elapsed=hours_elapsed,
        agent_outputs=agent_outputs,
        action_items=action_items,
        world_state=world_state,
    )
