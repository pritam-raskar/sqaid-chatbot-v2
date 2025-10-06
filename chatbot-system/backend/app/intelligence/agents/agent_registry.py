"""
Agent Registry for managing specialized agents.
Provides centralized access to SQLAgent, APIAgent, SOAPAgent.
"""
from typing import Dict, Optional
import logging

from app.intelligence.agents.base_agent import BaseAgent
from app.intelligence.orchestration.types import AgentType

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for managing specialized agents.

    Responsibilities:
    - Register agents by type
    - Retrieve agents for execution
    - List available agents
    - Validate agent availability

    Usage:
        registry = AgentRegistry()
        registry.register(AgentType.SQL_AGENT, sql_agent)

        agent = registry.get_agent(AgentType.SQL_AGENT)
        result = await agent.execute("Count all alerts")
    """

    def __init__(self):
        """Initialize empty agent registry"""
        self.agents: Dict[AgentType, BaseAgent] = {}
        logger.info("🔧 Initialized AgentRegistry")

    def register(self, agent_type: AgentType, agent: BaseAgent) -> None:
        """
        Register an agent.

        Args:
            agent_type: Type of agent (SQL, API, SOAP)
            agent: Agent instance

        Raises:
            ValueError: If agent already registered for this type
        """
        if agent_type in self.agents:
            logger.warning(f"⚠️ Agent already registered for {agent_type.value}, replacing...")

        self.agents[agent_type] = agent
        logger.info(
            f"✅ Registered {agent_type.value} with "
            f"{len(agent.get_available_tools())} tools"
        )

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        """
        Get agent by type.

        Args:
            agent_type: Type of agent to retrieve

        Returns:
            Agent instance or None if not registered
        """
        agent = self.agents.get(agent_type)
        if not agent:
            logger.warning(f"⚠️ Agent not found for type: {agent_type.value}")
        else:
            logger.debug(f"📋 Retrieved agent: {agent_type.value}")
        return agent

    def has_agent(self, agent_type: AgentType) -> bool:
        """Check if agent is registered"""
        return agent_type in self.agents

    def list_agents(self) -> Dict[str, Dict[str, any]]:
        """
        List all registered agents with metadata.

        Returns:
            Dict of agent_type -> metadata
        """
        result = {}
        for agent_type, agent in self.agents.items():
            result[agent_type.value] = {
                "type": agent_type.value,
                "tools_count": len(agent.get_available_tools()),
                "tools": agent.get_available_tools(),
                "data_source": agent.data_source_filter.value if agent.data_source_filter else "all"
            }

        logger.debug(f"📊 Listed {len(result)} registered agents")
        return result

    def unregister(self, agent_type: AgentType) -> bool:
        """
        Unregister an agent.

        Args:
            agent_type: Type of agent to remove

        Returns:
            True if removed, False if not found
        """
        if agent_type in self.agents:
            del self.agents[agent_type]
            logger.info(f"🗑️ Unregistered {agent_type.value}")
            return True

        logger.warning(f"⚠️ Cannot unregister {agent_type.value}: not found")
        return False

    def clear(self) -> None:
        """Remove all agents"""
        count = len(self.agents)
        self.agents.clear()
        logger.info(f"🧹 Cleared {count} agents from registry")

    def get_agent_count(self) -> int:
        """Get count of registered agents"""
        return len(self.agents)

    def __repr__(self) -> str:
        """String representation of registry"""
        agent_types = [agent_type.value for agent_type in self.agents.keys()]
        return f"AgentRegistry(agents={agent_types})"
