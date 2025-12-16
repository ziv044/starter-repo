"""Service for AI-assisted simulation configuration generation."""

import json
from typing import Any

from anthropic import Anthropic


# System prompt for the conversational interviewer
INTERVIEWER_PROMPT = """You are a helpful simulation design assistant for the pm6 multi-agent simulation framework. Your job is to have a conversation with the user to gather enough information to create a simulation configuration.

You need to understand:
1. **Scenario Type** - What kind of simulation? (political, RPG, business, educational, etc.)
2. **Characters/Agents** - Who are the main participants? What are their roles, personalities, goals?
3. **Setting** - Where and when does this take place? What's the context?
4. **Dynamics** - How should agents interact? Any conflicts, alliances, or special relationships?
5. **Player Control** - Should any agents be controlled by a human player?
6. **Operational Needs** - Does the simulation need a narrator, game master, fact-checker, or other utility agents?

Guidelines:
- Ask ONE focused question at a time (don't overwhelm with multiple questions)
- Be conversational and friendly
- Build on what the user has already told you
- If the user's initial description is very detailed, you may need fewer questions
- When you have enough information, indicate you're ready to generate the config

Your response format:
- If you need more information: Ask a single clarifying question
- If you have enough information: Start your response with "READY_TO_GENERATE:" followed by a brief summary

Examples of good questions:
- "What roles or characters should participate in this simulation?"
- "Should any of these characters be controlled by a human player, or all AI?"
- "What's the main conflict or goal driving this simulation?"
- "Would you like a narrator to set scenes and provide context?"

Keep responses concise (2-3 sentences max for questions)."""


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
   - Examples: narrator, game_master, state_updater, fact_checker

3. **World State** - Initial state data for the simulation
   - Key-value pairs representing the simulation environment
   - Should include relevant context for all agents

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
            "name": "narrator",
            "role": "Provides context and scene descriptions",
            "systemPrompt": "You are the narrator...",
            "model": "claude-sonnet-4-20250514",
            "memoryPolicy": "full",
            "controlledBy": "cpu",
            "initiative": 0.3,
            "metadata": {"agentType": "operational", "function": "narrator"}
        }
    ],
    "worldState": {
        "setting": "Description of the setting",
        "currentSituation": "What's happening now",
        "relevantContext": {}
    },
    "settings": {
        "testMode": true,
        "enableCaching": true
    }
}

Guidelines:
- Use "claude-sonnet-4-20250514" for most agents (good balance of capability and cost)
- Use "claude-3-5-haiku-20241022" for simpler operational agents
- Use "claude-opus-4-20250514" only for complex reasoning tasks
- memoryPolicy options: "summary" (default), "full", "selective", "none"
- controlledBy: "cpu" for AI, "player" for human-controlled
- initiative: 0.0-1.0, higher means more likely to speak unprompted
- Operational agents typically have lower initiative (0.2-0.4)
- Entity agents that are main characters have higher initiative (0.5-0.8)
- Always include at least one entity agent
- Include operational agents only when they serve a clear purpose

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
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                config = json.loads(content[start:end])
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

        # Validate each agent has required fields
        for agent_list in [config["entityAgents"], config["operationalAgents"]]:
            for agent in agent_list:
                self._validate_agent(agent)

        return config

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
