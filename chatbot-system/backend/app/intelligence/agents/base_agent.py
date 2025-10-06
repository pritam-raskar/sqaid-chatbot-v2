"""
Base Agent class for specialized agents in LangGraph Multi-Agent Orchestration.
Provides common functionality for SQLAgent, APIAgent, and SOAPAgent.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
import time
from datetime import datetime

from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.intelligence.orchestration.types import (
    AgentState,
    AgentResult,
    AgentType,
    DataSourceType
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents.

    Responsibilities:
    - Filter tools from registry by data source
    - Execute queries using filtered tools
    - Format results in standard AgentResult format
    - Track performance metrics
    - Handle errors gracefully

    Subclasses must implement:
    - _execute_query(): Main query execution logic
    """

    def __init__(
        self,
        agent_type: AgentType,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        data_source_filter: Optional[DataSourceType] = None
    ):
        """
        Initialize base agent.

        Args:
            agent_type: Type of agent (SQL, API, SOAP)
            llm_provider: LLM provider (Anthropic, OpenAI, etc.)
            tool_registry: Registry with all available tools
            data_source_filter: Filter tools by data source type
        """
        self.agent_type = agent_type
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.data_source_filter = data_source_filter

        # Filter tools by data source
        self.tools = self._filter_tools()

        logger.info(
            f"🔧 Initialized {agent_type.value} with {len(self.tools)} tools "
            f"(filter: {data_source_filter.value if data_source_filter else 'none'})"
        )

    def _filter_tools(self) -> Dict[str, Any]:
        """
        Filter tools from registry based on data source type.

        Returns:
            Dict of tool_name -> tool instance

        Example:
            # For SQLAgent, only get PostgreSQL tools
            tools = self._filter_tools()  # Returns 6 PostgreSQL tools
        """
        if not self.data_source_filter:
            # No filter, return all tools
            logger.debug("No data source filter, using all tools")
            return self.tool_registry.tools

        filtered = {}
        for tool_name, tool in self.tool_registry.tools.items():
            metadata = self.tool_registry.metadata.get(tool_name)
            if metadata and metadata.data_source == self.data_source_filter:
                filtered[tool_name] = tool
                logger.debug(f"  ✓ Included tool: {tool_name}")

        logger.info(
            f"📊 Filtered {len(filtered)} tools for {self.data_source_filter.value} "
            f"(from {len(self.tool_registry.tools)} total)"
        )

        return filtered

    async def execute(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute a query using this agent.

        Args:
            query: Natural language query or specific request
            context: Additional context (previous results, user preferences, etc.)
            parameters: Specific parameters for tools

        Returns:
            AgentResult with data, metadata, and performance info

        Flow:
            1. Log query
            2. Start timer
            3. Call _execute_query() (subclass implementation)
            4. Format result
            5. Track performance
            6. Handle errors
        """
        logger.info(f"▶️ [{self.agent_type.value}] Executing: {query[:100]}...")
        start_time = time.time()

        try:
            # Call subclass implementation
            result_data = await self._execute_query(query, context, parameters)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Format result
            result: AgentResult = {
                "agent_type": self.agent_type,
                "tool_name": self._get_tool_name_used(),
                "data": result_data,
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "query": query,
                    "context": context or {},
                    "row_count": self._get_row_count(result_data)
                },
                "error": None,
                "execution_time_ms": execution_time_ms
            }

            logger.info(
                f"✅ [{self.agent_type.value}] Completed in {execution_time_ms:.2f}ms, "
                f"{result['metadata']['row_count']} results"
            )

            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            error_msg = f"{self.agent_type.value} execution failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)

            # Return error result
            return {
                "agent_type": self.agent_type,
                "tool_name": None,
                "data": None,
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "query": query
                },
                "error": error_msg,
                "execution_time_ms": execution_time_ms
            }

    @abstractmethod
    async def _execute_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Main query execution logic - MUST be implemented by subclass.

        Args:
            query: Natural language query
            context: Additional context
            parameters: Tool parameters

        Returns:
            Raw result data (will be wrapped in AgentResult by execute())

        Example for SQLAgent:
            async def _execute_query(self, query, context, parameters):
                sql = self.generate_sql(query)
                result = await self.db_adapter.execute_query(sql)
                return result

        Example for APIAgent:
            async def _execute_query(self, query, context, parameters):
                endpoint = self.select_endpoint(query)
                result = await self.call_endpoint(endpoint, parameters)
                return result
        """
        pass

    def _get_tool_name_used(self) -> Optional[str]:
        """
        Get name of tool that was used (override in subclass if needed).

        Returns:
            Tool name or None
        """
        return None

    def _get_row_count(self, data: Any) -> int:
        """
        Get count of rows/items in result data.

        Args:
            data: Result data (list, dict, etc.)

        Returns:
            Count of items
        """
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            # Check for common count keys
            if "count" in data:
                return data["count"]
            elif "total" in data:
                return data["total"]
            elif "results" in data and isinstance(data["results"], list):
                return len(data["results"])
            return 1
        elif data is None:
            return 0
        else:
            return 1

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names for this agent"""
        return list(self.tools.keys())

    def get_tool_descriptions(self) -> List[str]:
        """Get descriptions of available tools"""
        descriptions = []
        for tool_name, tool in self.tools.items():
            descriptions.append(f"- {tool_name}: {tool.description}")
        return descriptions
