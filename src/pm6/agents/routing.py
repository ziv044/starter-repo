"""Agent routing - determines which agents handle which situations."""

from typing import Any

from pm6.agents.agentConfig import AgentConfig


class AgentRouter:
    """Routes interactions to appropriate agents.

    The router determines which agent(s) should respond to a given
    situation based on situation types and agent configuration.

    Args:
        agents: Dictionary of agent name to AgentConfig.
    """

    def __init__(self, agents: dict[str, AgentConfig] | None = None):
        self._agents: dict[str, AgentConfig] = agents or {}
        self._situationIndex: dict[str, list[str]] = {}
        self._rebuildIndex()

    def _rebuildIndex(self) -> None:
        """Rebuild the situation type to agent index."""
        self._situationIndex.clear()
        for agentName, config in self._agents.items():
            for situationType in config.situationTypes:
                if situationType not in self._situationIndex:
                    self._situationIndex[situationType] = []
                self._situationIndex[situationType].append(agentName)

    def addAgent(self, config: AgentConfig) -> None:
        """Add an agent to the router.

        Args:
            config: The agent configuration.
        """
        self._agents[config.name] = config
        self._rebuildIndex()

    def removeAgent(self, agentName: str) -> None:
        """Remove an agent from the router.

        Args:
            agentName: Name of the agent to remove.
        """
        if agentName in self._agents:
            del self._agents[agentName]
            self._rebuildIndex()

    def getAgent(self, agentName: str) -> AgentConfig | None:
        """Get an agent by name.

        Args:
            agentName: Name of the agent.

        Returns:
            AgentConfig if found, None otherwise.
        """
        return self._agents.get(agentName)

    def hasAgent(self, agentName: str) -> bool:
        """Check if an agent exists.

        Args:
            agentName: Name of the agent.

        Returns:
            True if agent exists.
        """
        return agentName in self._agents

    def getAgentsForSituation(self, situationType: str) -> list[AgentConfig]:
        """Get all agents that handle a situation type.

        Args:
            situationType: The type of situation.

        Returns:
            List of agents that can handle this situation.
        """
        agentNames = self._situationIndex.get(situationType, [])
        return [self._agents[name] for name in agentNames if name in self._agents]

    def getAllAgents(self) -> list[AgentConfig]:
        """Get all registered agents.

        Returns:
            List of all agent configurations.
        """
        return list(self._agents.values())

    def routeInteraction(
        self,
        agentName: str | None = None,
        situationType: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[AgentConfig]:
        """Route an interaction to appropriate agent(s).

        If agentName is provided, routes to that specific agent.
        Otherwise, uses situationType to find relevant agents.

        Args:
            agentName: Specific agent to route to (optional).
            situationType: Type of situation for routing (optional).
            context: Additional context for routing decisions (optional).

        Returns:
            List of agents that should handle this interaction.
        """
        # Direct routing by name
        if agentName:
            agent = self.getAgent(agentName)
            return [agent] if agent else []

        # Route by situation type
        if situationType:
            return self.getAgentsForSituation(situationType)

        # No routing criteria - return empty
        return []
