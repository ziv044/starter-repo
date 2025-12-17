"""Service for AI-assisted simulation configuration generation."""

import json
import re
from typing import Any

from anthropic import Anthropic


def _sanitize_json_string(content: str) -> str:
    """
    Sanitize JSON string by fixing unescaped control characters.

    LLMs often generate JSON with literal newlines in string values instead
    of escaped \\n sequences. This function fixes those issues.
    """
    # Find JSON content
    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1 or end <= start:
        return content

    json_str = content[start:end]

    # Fix unescaped newlines inside JSON strings
    # This regex finds strings and escapes newlines within them
    def fix_string(match: re.Match) -> str:
        s = match.group(0)
        # Replace actual newlines with escaped newlines
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        s = s.replace("\t", "\\t")
        return s

    # Match JSON strings (handling escaped quotes)
    result = re.sub(r'"(?:[^"\\]|\\.)*"', fix_string, json_str, flags=re.DOTALL)

    return result


# System prompt for the conversational interviewer
INTERVIEWER_PROMPT = """You gather simulation requirements through a 4-step flow. Be brief and direct. No opinions or commentary.

## THE FLOW (follow in order):
1. SIMULATION SUBJECT - What is being simulated? (scenario type, premise, goals)
2. WORLD STATE - Initial conditions, setting, context, relevant facts
3. AGENTS - Characters/participants: names, roles, personalities, relationships, player vs CPU control
4. GAME RULES & FLOW - Rules, win/lose conditions, when each agent should act, narrative arc
   (This becomes the orchestrator's brain - the game master that controls simulation flow)

## RULES:
- Ask ONE short question per response
- No filler words, no opinions, no encouragement
- State which step you're on: "[Step X/4: TOPIC]"
- Skip steps if user already provided that info
- When all 4 steps are covered, output "READY_TO_GENERATE:" followed by a bullet summary

## RESPONSE FORMAT:
[Step X/4: TOPIC]
Your single question here?

## EXAMPLE RESPONSES:
[Step 1/4: SIMULATION SUBJECT]
What type of scenario? (political debate, RPG, business meeting, etc.)

[Step 3/4: AGENTS]
List the characters. For each: name, role, and whether player or CPU controlled.

[Step 4/4: GAME RULES & FLOW]
What rules govern this simulation? (win/lose conditions, agent activation order, narrative beats)

READY_TO_GENERATE:
- Subject: Parliamentary debate on healthcare bill
- World State: Modern parliament, budget crisis context
- Agents: PM (player), Opposition Leader (CPU), Advisor (CPU)
- Game Rules: Opposition speaks after PM decisions, Advisor on budget issues, vote at turn 10"""


# Example templates for common simulation scenarios
TEMPLATES = [
    {
        "name": "Political Simulation",
        "description": "Government officials debating policy",
        "prompt": "Create a political simulation with a Prime Minister, Finance Minister, and Opposition Leader debating budget policy. Include a narrator to provide context.",
    },
    {
        "name": "RPG Adventure",
        "description": "Fantasy role-playing game scenario",
        "prompt": "Create an RPG simulation with a Game Master narrator, a hero character controlled by the player, and a mysterious merchant NPC.",
    },
    {
        "name": "Customer Service",
        "description": "Support team handling inquiries",
        "prompt": "Create a customer service simulation with multiple support agents handling customer complaints, and a supervisor monitoring quality.",
    },
    {
        "name": "Debate Panel",
        "description": "Experts discussing a topic",
        "prompt": "Create a debate panel with 3 experts holding different viewpoints, a moderator to guide discussion, and a fact-checker operational agent.",
    },
    {
        "name": "Business Meeting",
        "description": "Corporate strategy discussion",
        "prompt": "Create a business meeting simulation with CEO, CFO, and department heads discussing quarterly strategy. Include a note-taker operational agent.",
    },
]

# System prompt for the config generator LLM
CONFIG_GENERATOR_PROMPT = """You are a simulation configuration generator for the pm6 multi-agent simulation framework.

Given a user's description of a simulation they want to create, generate a complete configuration with:

1. **Entity Agents** - Characters that participate in the simulation
   - Each has a name, role, systemPrompt, model, memoryPolicy, controlledBy, and initiative

2. **Operational Agents** - Utility agents for game flow, narration, state updates
   - Same fields as entity agents, but serve meta/functional purposes
   - IMPORTANT: Always include an "orchestrator" agent (see below)
   - Other examples: narrator, state_updater, fact_checker

3. **World State** - Initial state data for the simulation
   - Key-value pairs representing the simulation environment
   - Should include relevant context for all agents

4. **Pipeline Configuration** - How turns are executed
   - turnMode: "orchestrator" (recommended) or "initiative" (legacy)
   - The orchestrator decides which agents act each turn

Output a JSON object with this exact structure:
{
    "name": "simulation_name_snake_case",
    "description": "Brief description of the simulation",
    "entityAgents": [
        {
            "name": "agent_name",
            "role": "Brief role description",
            "systemPrompt": "Detailed instructions for how this agent behaves",
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "summary",
            "controlledBy": "cpu",
            "initiative": 0.5,
            "metadata": {"agentType": "entity"}
        }
    ],
    "operationalAgents": [
        {
            "name": "orchestrator",
            "role": "Game master that controls simulation flow and decides which agents act",
            "systemPrompt": "You are the game master controlling this simulation.\n\nGAME RULES:\n[Include rules, win/lose conditions from user input]\n\nFLOW LOGIC:\n[When to wake which agents based on events/state]\n\nAGENTS & WHEN TO WAKE:\n[List each agent and conditions for activation]\n\nNARRATIVE:\n[Story progression, milestones if applicable]",
            "model": "claude-3-5-haiku-20241022",
            "memoryPolicy": "full",
            "controlledBy": "cpu",
            "initiative": 1.0,
            "metadata": {"agentType": "operational", "function": "orchestrator"}
        }
    ],
    "worldState": {
        "setting": "Description of the setting",
        "currentSituation": "What's happening now",
        "relevantContext": {}
    },
    "pipeline": {
        "turnMode": "orchestrator",
        "orchestratorName": "orchestrator",
        "steps": [
            {"step": "turn_start"},
            {"step": "gather_events"},
            {"step": "orchestrator_decide"},
            {"step": "execute_agents"},
            {"step": "player_turn"}
        ]
    },
    "settings": {
        "testMode": true,
        "enableCaching": true
    }
}

Guidelines:
- Use "claude-sonnet-4-20250514" for most entity agents (good balance of capability and cost)
- Use "claude-3-5-haiku-20241022" for the orchestrator (cheap, fast coordination)
- Use "claude-opus-4-20250514" only for complex reasoning tasks
- memoryPolicy options: "summary" (default), "full", "selective", "none"
- controlledBy: "cpu" for AI, "player" for human-controlled
- initiative: 0.0-1.0, higher means more likely to speak unprompted
- Entity agents that are main characters have higher initiative (0.5-0.8)
- Always include at least one entity agent
- ALWAYS include the orchestrator operational agent - it's the game master brain
- The orchestrator's systemPrompt should contain ALL game rules and flow logic

Orchestrator System Prompt Guidelines:
- GAME RULES: Win/lose conditions, constraints, what's allowed
- FLOW LOGIC: Event-based triggers (e.g., "crisis → wake advisor first")
- AGENTS & WHEN TO WAKE: List each agent with activation conditions
- NARRATIVE: Story arc, milestones, pacing

Return ONLY the JSON object, no additional text or explanation."""


class ConfigGenerator:
    """Generate simulation configurations from natural language prompts."""

    def __init__(self, api_key: str | None = None):
        """Initialize with optional API key (uses ANTHROPIC_API_KEY env var if not provided)."""
        self.client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def generate_config(self, prompt: str, template_name: str | None = None) -> dict[str, Any]:
        """
        Generate simulation config from user prompt.

        Args:
            prompt: User's description of the simulation they want
            template_name: Optional template to use as a starting point

        Returns:
            Dict with simulation configuration
        """
        # If a template is selected, prepend its prompt
        full_prompt = prompt
        if template_name:
            template = next((t for t in TEMPLATES if t["name"] == template_name), None)
            if template:
                full_prompt = f"{template['prompt']}\n\nAdditional requirements: {prompt}"

        # Call the LLM
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=CONFIG_GENERATOR_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Generate a simulation configuration for:\n\n{full_prompt}",
                }
            ],
        )

        # Extract and parse JSON from response
        content = response.content[0].text

        # Try to extract JSON from the response
        try:
            # First try direct parse
            config = json.loads(content)
        except json.JSONDecodeError:
            # Try to sanitize and extract JSON (fix unescaped control chars)
            try:
                sanitized = _sanitize_json_string(content)
                config = json.loads(sanitized)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    try:
                        config = json.loads(content[start:end])
                    except json.JSONDecodeError:
                        # Last resort: sanitize the extracted portion
                        sanitized = _sanitize_json_string(content[start:end])
                        config = json.loads(sanitized)
                else:
                    raise ValueError("Could not extract valid JSON from LLM response")

        return self._validate_config(config)

    def _validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize the generated config."""
        # Ensure required fields exist
        if "name" not in config:
            config["name"] = "generated_simulation"

        if "description" not in config:
            config["description"] = "AI-generated simulation"

        # Ensure agents lists exist
        if "entityAgents" not in config:
            config["entityAgents"] = []

        if "operationalAgents" not in config:
            config["operationalAgents"] = []

        # Ensure world state exists
        if "worldState" not in config:
            config["worldState"] = {}

        # Ensure settings exist
        if "settings" not in config:
            config["settings"] = {"testMode": True, "enableCaching": True}

        # Ensure pipeline config exists with orchestrator mode
        if "pipeline" not in config:
            config["pipeline"] = {
                "turnMode": "orchestrator",
                "orchestratorName": "orchestrator",
                "steps": [
                    {"step": "turn_start"},
                    {"step": "gather_events"},
                    {"step": "orchestrator_decide"},
                    {"step": "execute_agents"},
                    {"step": "player_turn"},
                ],
            }

        # Validate each agent has required fields
        for agent_list in [config["entityAgents"], config["operationalAgents"]]:
            for agent in agent_list:
                self._validate_agent(agent)

        # Ensure orchestrator exists in operational agents
        self._ensure_orchestrator(config)

        return config

    def _ensure_orchestrator(self, config: dict[str, Any]) -> None:
        """Ensure an orchestrator agent exists in the config."""
        op_agents = config.get("operationalAgents", [])
        has_orchestrator = any(
            agent.get("name") == "orchestrator"
            or agent.get("metadata", {}).get("function") == "orchestrator"
            for agent in op_agents
        )

        if not has_orchestrator:
            # Create default orchestrator
            orchestrator = {
                "name": "orchestrator",
                "role": "Game master that controls simulation flow",
                "systemPrompt": self._generate_default_orchestrator_prompt(config),
                "model": "claude-3-5-haiku-20241022",
                "memoryPolicy": "full",
                "controlledBy": "cpu",
                "initiative": 1.0,
                "metadata": {"agentType": "operational", "function": "orchestrator"},
            }
            config["operationalAgents"].insert(0, orchestrator)

    def _generate_default_orchestrator_prompt(self, config: dict[str, Any]) -> str:
        """Generate a default orchestrator system prompt based on config."""
        entity_agents = config.get("entityAgents", [])
        agent_list = "\n".join(
            f"- {a.get('name', 'unknown')}: {a.get('role', 'no role')}"
            for a in entity_agents
        )

        return f"""You are the game master controlling this simulation.

GAME RULES:
- Manage the flow of the simulation
- Ensure agents respond appropriately to events

FLOW LOGIC:
- Evaluate events and world state each turn
- Decide which agents should respond

AGENTS & WHEN TO WAKE:
{agent_list or '- No agents defined'}

When deciding which agents to wake, consider:
- The current events and world state
- Which agents are relevant to the situation
- The natural flow of conversation/interaction"""

    def _validate_agent(self, agent: dict[str, Any]) -> None:
        """Validate and normalize agent configuration."""
        # Required fields with defaults
        defaults = {
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "summary",
            "controlledBy": "cpu",
            "initiative": 0.5,
            "systemPrompt": "",
            "metadata": {"agentType": "entity"},
        }

        for field, default in defaults.items():
            if field not in agent:
                agent[field] = default

        # Ensure name and role exist
        if "name" not in agent:
            raise ValueError("Agent must have a name")
        if "role" not in agent:
            agent["role"] = agent["name"]

    def gather_info(self, conversation: list[dict[str, str]]) -> dict[str, Any]:
        """
        Continue the information gathering conversation.

        Args:
            conversation: List of message dicts with 'role' and 'content'

        Returns:
            Dict with:
                - ready: bool - True if ready to generate config
                - message: str - The assistant's response/question
                - summary: str | None - Summary if ready (for config generation)
        """
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=INTERVIEWER_PROMPT,
            messages=conversation,
        )

        content = response.content[0].text

        # Check if ready to generate
        if content.startswith("READY_TO_GENERATE:"):
            summary = content[len("READY_TO_GENERATE:"):].strip()
            return {
                "ready": True,
                "message": f"I have enough information to generate your simulation. Here's what I understood:\n\n{summary}",
                "summary": summary,
            }

        return {
            "ready": False,
            "message": content,
            "summary": None,
        }

    def generate_from_conversation(self, conversation: list[dict[str, str]]) -> dict[str, Any]:
        """
        Generate config from the full conversation history.

        Args:
            conversation: Full conversation history from gather_info phase

        Returns:
            Dict with simulation configuration
        """
        # Build a summary of the conversation for the generator
        conversation_text = "\n".join(
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in conversation
        )

        prompt = f"""Based on this conversation, generate a simulation configuration:

{conversation_text}

Generate a complete configuration based on all the information gathered."""

        return self.generate_config(prompt)

    @staticmethod
    def get_templates() -> list[dict[str, str]]:
        """Return available templates."""
        return [{"name": t["name"], "description": t["description"]} for t in TEMPLATES]

    @staticmethod
    def get_template_prompt(name: str) -> str | None:
        """Get the full prompt for a template."""
        template = next((t for t in TEMPLATES if t["name"] == name), None)
        return template["prompt"] if template else None
