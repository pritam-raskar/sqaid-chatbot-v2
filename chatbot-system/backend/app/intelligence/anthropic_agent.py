"""
Anthropic Agent that integrates tools with the Anthropic API
"""
import json
import logging
from typing import Dict, List, Any, Optional
from app.intelligence.tool_registry import ToolRegistry
from app.llm.providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


class AnthropicAgent:
    """Agent that uses Anthropic's native tool calling with registered tools"""

    def __init__(self, llm_provider: AnthropicProvider, tool_registry: ToolRegistry):
        """
        Initialize Anthropic agent

        Args:
            llm_provider: Anthropic LLM provider instance
            tool_registry: Registry containing available tools
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.tools = {}  # Map of tool name to tool instance

        # Convert LangChain tools to Anthropic tool format
        self.anthropic_tools = []
        self._convert_tools_to_anthropic_format()

    def _convert_tools_to_anthropic_format(self) -> None:
        """Convert registered LangChain tools to Anthropic's tool format"""
        for tool_name, tool_info in self.tool_registry.tools.items():
            tool = tool_info['tool']
            self.tools[tool_name] = tool

            # Extract parameters from the tool's args_schema
            parameters = {}
            required = []

            if hasattr(tool, 'args_schema'):
                schema = tool.args_schema
                if hasattr(schema, '__fields__'):
                    for field_name, field_info in schema.__fields__.items():
                        # Get field type and description
                        field_type = "string"  # Default to string
                        if field_info.annotation:
                            if field_info.annotation == int:
                                field_type = "integer"
                            elif field_info.annotation == float:
                                field_type = "number"
                            elif field_info.annotation == bool:
                                field_type = "boolean"

                        parameters[field_name] = {
                            "type": field_type,
                            "description": field_info.field_info.description or f"Parameter {field_name}"
                        }

                        # Check if field is required
                        if field_info.is_required():
                            required.append(field_name)

            # Create Anthropic tool definition
            anthropic_tool = {
                "name": tool_name,
                "description": tool.description or f"Tool {tool_name}",
                "input_schema": {
                    "type": "object",
                    "properties": parameters,
                    "required": required
                }
            }

            self.anthropic_tools.append(anthropic_tool)

        logger.info(f"Converted {len(self.anthropic_tools)} tools to Anthropic format")

    async def process_message(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user message with tool calling capabilities

        Args:
            message: User's message
            session_id: Optional session ID for context

        Returns:
            Agent response with tool results if applicable
        """
        try:
            # Initial call to Anthropic with tools
            messages = [{"role": "user", "content": message}]

            response = await self._call_anthropic_with_tools(messages)

            # Check if tools were called
            if self._has_tool_calls(response):
                # Execute tools and get results
                tool_results = await self._execute_tools(response)

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": response.get("content", [])
                })

                # Add tool results as user message
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Get final response from Anthropic
                final_response = await self._call_anthropic_with_tools(messages)

                return {
                    "content": self._extract_text_content(final_response),
                    "tool_calls": tool_results,
                    "raw_response": final_response
                }
            else:
                # No tools called, return direct response
                return {
                    "content": self._extract_text_content(response),
                    "tool_calls": None,
                    "raw_response": response
                }

        except Exception as e:
            logger.error(f"Error in Anthropic agent: {e}")
            return {
                "content": f"Error processing request: {str(e)}",
                "tool_calls": None,
                "error": str(e)
            }

    async def _call_anthropic_with_tools(self, messages: List[Dict]) -> Dict:
        """Call Anthropic API with tools enabled"""
        try:
            # Prepare the request with tools
            response = await self.llm_provider.client.messages.create(
                model=self.llm_provider.model,
                messages=messages,
                tools=self.anthropic_tools if self.anthropic_tools else None,
                max_tokens=4096
            )

            # Convert response to dict
            return {
                "content": response.content,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else 0,
                    "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0
                }
            }
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise

    def _has_tool_calls(self, response: Dict) -> bool:
        """Check if response contains tool calls"""
        content = response.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    return True
        return False

    async def _execute_tools(self, response: Dict) -> List[Dict]:
        """Execute tool calls from Anthropic response"""
        tool_results = []
        content = response.get("content", [])

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tool_name = item.get("name")
                    tool_input = item.get("input", {})
                    tool_id = item.get("id")

                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

                    if tool_name in self.tools:
                        try:
                            tool = self.tools[tool_name]

                            # Execute tool (handle both sync and async)
                            if hasattr(tool, '_arun'):
                                result = await tool._arun(**tool_input)
                            elif hasattr(tool, '_run'):
                                result = tool._run(**tool_input)
                            else:
                                result = f"Tool {tool_name} has no executable method"

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": str(result)
                            })

                        except Exception as e:
                            logger.error(f"Tool execution failed for {tool_name}: {e}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": f"Error executing tool: {str(e)}",
                                "is_error": True
                            })
                    else:
                        logger.warning(f"Tool {tool_name} not found in registry")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Tool {tool_name} not found",
                            "is_error": True
                        })

        return tool_results

    def _extract_text_content(self, response: Dict) -> str:
        """Extract text content from Anthropic response"""
        content = response.get("content", [])

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return " ".join(text_parts)

        return ""

    def get_tool_descriptions(self) -> List[str]:
        """Get descriptions of all available tools"""
        descriptions = []
        for tool in self.anthropic_tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")
        return descriptions