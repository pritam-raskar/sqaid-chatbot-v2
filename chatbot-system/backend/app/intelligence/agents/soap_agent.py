"""
SOAP Agent - Handles SOAP service queries.
Wraps existing SOAP tools from the tool registry.
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


class SOAPAgent(BaseAgent):
    """
    Specialized agent for SOAP service queries.

    Capabilities:
    - SOAP operation selection
    - Parameter mapping and validation
    - XML request/response handling
    - Service fault handling

    Architecture:
        User Query → Analyze Intent → Select Operation →
        Map Parameters → Execute SOAP Call → Parse Response

    Example Queries:
        - "Get customer details for ID 12345"
        - "Process payment for account 67890"
        - "Validate account status for account ABC123"
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry
    ):
        """
        Initialize SOAP Agent.

        Args:
            llm_provider: LLM for intent analysis
            tool_registry: Registry with SOAP tools

        Steps:
            1. Initialize base agent with SOAP API filter
            2. Create filtered tool registry with only SOAP tools
            3. Initialize UniversalAgent wrapper
        """
        # Initialize base agent with SOAP API filter
        super().__init__(
            agent_type=AgentType.SOAP_AGENT,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            data_source_filter=DataSourceType.SOAP_API
        )

        self.last_tool_used = None

        # Create filtered tool registry
        logger.info(f"🔧 Creating filtered tool registry for SOAP services...")
        self.soap_tool_registry = self._create_filtered_registry()

        # Create UniversalAgent wrapper
        logger.info(f"🤖 Creating UniversalAgent wrapper...")
        self.universal_agent = UniversalAgent(
            llm_provider=llm_provider,
            tool_registry=self.soap_tool_registry
        )

        logger.info(
            f"✅ SOAPAgent initialized with {len(self.tools)} SOAP operations"
        )

    def _create_filtered_registry(self) -> ToolRegistry:
        """
        Create registry with only SOAP tools.

        Returns:
            ToolRegistry with filtered SOAP tools
        """
        from app.intelligence.tool_registry import ToolRegistry

        filtered_registry = ToolRegistry()

        for tool_name, tool in self.tools.items():
            metadata = self.tool_registry.metadata.get(tool_name)
            if metadata:
                filtered_registry.tools[tool_name] = tool
                filtered_registry.metadata[tool_name] = metadata
                logger.debug(f"  ✓ Added SOAP tool: {tool_name}")

        logger.info(f"📊 Created filtered registry with {len(filtered_registry.tools)} SOAP tools")
        return filtered_registry

    async def _execute_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Execute SOAP query using UniversalAgent.

        Args:
            query: Natural language query
            context: Additional context
            parameters: SOAP operation parameters

        Returns:
            SOAP response data

        Flow:
            1. Build enriched query with parameters
            2. Call UniversalAgent
            3. Parse SOAP response
            4. Return formatted data
        """
        logger.info(f"🔍 [SOAPAgent] Processing: {query[:100]}...")

        enriched_query = self._build_query_with_parameters(query, context, parameters)
        logger.debug(f"📝 Enriched query: {enriched_query}")

        try:
            logger.info(f"⚙️ Invoking UniversalAgent for SOAP call...")
            result = await self.universal_agent.process_message(enriched_query)

            if result.get("tool_calls"):
                tool_results = result["tool_calls"]
                logger.debug(f"🔧 Tool calls made: {len(tool_results)}")

                if isinstance(tool_results, list) and len(tool_results) > 0:
                    first_result = tool_results[0]
                    if isinstance(first_result, dict):
                        data = first_result.get("result", first_result)
                        self.last_tool_used = first_result.get("tool")
                        logger.info(f"✅ [SOAPAgent] Successfully called {self.last_tool_used}")
                        return self._parse_soap_response(data)

            logger.warning(f"⚠️ No tool call made, returning content")
            return {"message": result.get("content", "")}

        except Exception as e:
            logger.error(f"❌ [SOAPAgent] Execution failed: {e}", exc_info=True)
            return {"error": str(e), "fault": "ServiceError"}

    def _build_query_with_parameters(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build enriched query with SOAP parameters.

        Args:
            query: Base query
            context: Additional context
            parameters: SOAP operation parameters

        Returns:
            Enriched query string
        """
        enriched = query

        if parameters:
            param_hints = ", ".join([f"{k}={v}" for k, v in parameters.items()])
            enriched += f" (SOAP Parameters: {param_hints})"
            logger.debug(f"📎 Added SOAP parameters: {param_hints}")

        if context and "operation" in context:
            enriched += f" (Operation: {context['operation']})"
            logger.debug(f"🔧 Added operation context")

        return enriched

    def _parse_soap_response(self, response: Any) -> Any:
        """
        Parse SOAP response into standard format.

        Args:
            response: Raw SOAP response (could be XML string, dict, etc.)

        Returns:
            Parsed response

        Handles:
        - XML strings → dicts
        - SOAP faults
        - Various data formats
        """
        # If already a dict or list, return as-is
        if isinstance(response, (dict, list)):
            logger.debug(f"✅ Response already structured ({type(response).__name__})")
            return response

        # Try to parse JSON string (some SOAP tools may return JSON)
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

    def get_available_operations(self) -> List[str]:
        """Get list of available SOAP operations"""
        return self.get_available_tools()

    def get_operation_description(self, operation_name: str) -> Optional[str]:
        """
        Get description of a specific SOAP operation.

        Args:
            operation_name: Name of the SOAP operation tool

        Returns:
            Description string or None
        """
        tool = self.tools.get(operation_name)
        if tool:
            return tool.description
        return None
