"""
API Agent - Handles REST API interactions using UniversalAgent.
Wraps existing REST API tools with specialized handling.
"""
from typing import Dict, Any, Optional, List
import logging
import json

from app.intelligence.agents.base_agent import BaseAgent
from app.intelligence.orchestration.types import AgentType, DataSourceType
from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.intelligence.universal_agent import UniversalAgent

logger = logging.getLogger(__name__)


class APIAgent(BaseAgent):
    """
    Specialized agent for REST API interactions.

    Capabilities:
    - Select appropriate REST endpoints based on query
    - Execute API calls with proper parameters
    - Handle API responses and errors
    - Format results consistently

    Architecture:
        User Query → UniversalAgent → REST Tool Selection →
        API Call → Response → Format → Return

    Example Queries:
        - "Get user information for john@example.com"
        - "List all departments"
        - "Get incident details for INC12345"
        - "Search for users in Engineering"
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry
    ):
        """
        Initialize API Agent.

        Args:
            llm_provider: LLM for natural language understanding
            tool_registry: Registry with all tools (will be filtered to REST only)

        Steps:
            1. Initialize base agent with REST API filter
            2. Create filtered tool registry (REST APIs only)
            3. Initialize UniversalAgent wrapper for tool calling
        """
        # Initialize base agent with REST API filter
        super().__init__(
            agent_type=AgentType.API_AGENT,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            data_source_filter=DataSourceType.REST_API
        )

        self.last_tool_used = None

        # Create a filtered tool registry with only API tools
        logger.info(f"🔧 Creating filtered tool registry for REST APIs...")
        self.api_tool_registry = self._create_filtered_registry()

        # Create UniversalAgent wrapper with API tools only
        logger.info(f"🤖 Creating UniversalAgent wrapper...")
        self.universal_agent = UniversalAgent(
            llm_provider=llm_provider,
            tool_registry=self.api_tool_registry
        )

        logger.info(
            f"✅ APIAgent initialized with {len(self.tools)} REST endpoints"
        )

    def _create_filtered_registry(self) -> ToolRegistry:
        """
        Create a tool registry containing only REST API tools.

        Returns:
            ToolRegistry with filtered tools

        This ensures UniversalAgent only sees REST API tools,
        not database or SOAP tools.
        """
        from app.intelligence.tool_registry import ToolRegistry

        filtered_registry = ToolRegistry()

        # Copy only REST API tools
        for tool_name, tool in self.tools.items():
            metadata = self.tool_registry.metadata.get(tool_name)
            if metadata:
                filtered_registry.tools[tool_name] = tool
                filtered_registry.metadata[tool_name] = metadata
                logger.debug(f"  ✓ Added API tool: {tool_name}")

        logger.info(f"📊 Created filtered registry with {len(filtered_registry.tools)} API tools")
        return filtered_registry

    async def _execute_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Execute API query using UniversalAgent.

        Args:
            query: Natural language query
            context: Additional context
            parameters: Specific parameters for API endpoint

        Returns:
            API response data

        Flow:
            1. Enrich query with context and parameters
            2. Call UniversalAgent (handles tool selection and calling)
            3. Extract result from UniversalAgent response
            4. Format and return

        Example:
            query: "Get user information for john@example.com"
            → UniversalAgent selects: rest_get_user_info
            → Calls with: {"user_id": "john@example.com"}
            → Returns: {"user_id": "123", "name": "John Doe", ...}
        """
        logger.info(f"🔍 [APIAgent] Processing: {query[:100]}...")

        # Build enriched query
        enriched_query = self._build_query_with_parameters(query, context, parameters)
        logger.debug(f"📝 Enriched query: {enriched_query}")

        try:
            # Use UniversalAgent to handle tool selection and execution
            logger.info(f"⚙️ Invoking UniversalAgent for API call...")
            result = await self.universal_agent.process_message(enriched_query)

            # Extract data from UniversalAgent response
            if result.get("tool_calls"):
                # Tool was called, extract data from tool results
                tool_results = result["tool_calls"]
                logger.debug(f"🔧 Tool calls made: {len(tool_results)}")

                if isinstance(tool_results, list) and len(tool_results) > 0:
                    # Get first tool result
                    first_result = tool_results[0]
                    if isinstance(first_result, dict):
                        data = first_result.get("result", first_result)
                        self.last_tool_used = first_result.get("tool")
                        logger.info(f"✅ [APIAgent] Successfully called {self.last_tool_used}")
                        return self._parse_api_response(data)

            # No tool call, return content as fallback
            logger.warning(f"⚠️ No tool call made, returning content")
            return {"message": result.get("content", "")}

        except Exception as e:
            logger.error(f"❌ [APIAgent] Execution failed: {e}", exc_info=True)
            return {"error": str(e)}

    def _build_query_with_parameters(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build enriched query with explicit parameters.

        Args:
            query: Base query
            context: Additional context
            parameters: Specific parameters

        Returns:
            Enriched query string

        Example:
            Input: query="Get user", parameters={"user_id": "john@example.com"}
            Output: "Get user information for user_id=john@example.com"
        """
        enriched = query

        if parameters:
            # Add parameters as hints for tool selection
            param_hints = ", ".join([f"{k}={v}" for k, v in parameters.items()])
            enriched += f" (Parameters: {param_hints})"
            logger.debug(f"📎 Added parameters: {param_hints}")

        if context and "filters" in context:
            enriched += f" (Filters: {context['filters']})"
            logger.debug(f"🔍 Added filters from context")

        return enriched

    def _parse_api_response(self, response: Any) -> Any:
        """
        Parse API response into standard format.

        Args:
            response: Raw API response (could be string, dict, list)

        Returns:
            Parsed response

        Handles:
        - JSON strings → dicts
        - Error responses
        - Various data formats
        """
        # If already a dict or list, return as-is
        if isinstance(response, (dict, list)):
            logger.debug(f"✅ Response already structured ({type(response).__name__})")
            return response

        # Try to parse JSON string
        if isinstance(response, str):
            try:
                parsed = json.loads(response)
                logger.debug(f"✅ Parsed JSON string to {type(parsed).__name__}")
                return parsed
            except json.JSONDecodeError:
                logger.debug(f"⚠️ Could not parse as JSON, returning as text")
                return {"result": response}

        # Return as-is
        logger.debug(f"ℹ️ Returning response as-is ({type(response).__name__})")
        return response

    def _get_tool_name_used(self) -> Optional[str]:
        """Override to return the actual tool name used"""
        return self.last_tool_used

    def get_available_endpoints(self) -> List[str]:
        """Get list of available REST API endpoints"""
        return self.get_available_tools()

    def get_endpoint_description(self, endpoint_name: str) -> Optional[str]:
        """
        Get description of a specific endpoint.

        Args:
            endpoint_name: Name of the endpoint tool

        Returns:
            Description string or None
        """
        tool = self.tools.get(endpoint_name)
        if tool:
            return tool.description
        return None
