"""
Universal Agent that works with any LLM provider supporting tool calling
"""
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.llm.streaming_helper import StreamingHelper

logger = logging.getLogger(__name__)


class UniversalAgent:
    """Agent that works with any LLM provider using a standard interface"""

    def __init__(self, llm_provider: BaseLLMProvider, tool_registry: ToolRegistry, session_manager=None):
        """
        Initialize universal agent

        Args:
            llm_provider: Any LLM provider implementing BaseLLMProvider
            tool_registry: Registry containing available tools
            session_manager: Optional SessionManager for retrieving conversation history
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.session_manager = session_manager
        self.tools = {}  # Map of tool name to tool instance
        self.tool_schemas = []  # Tool schemas in generic format

        # Convert tools to generic format
        self._prepare_tools()

    def _prepare_tools(self) -> None:
        """Prepare tools for use with any provider"""
        for tool_name, tool in self.tool_registry.tools.items():
            # tool is already a BaseTool instance
            self.tools[tool_name] = tool

            # Create generic tool schema
            tool_schema = self._create_generic_tool_schema(tool_name, tool)
            self.tool_schemas.append(tool_schema)

        logger.info(f"Prepared {len(self.tool_schemas)} tools for universal agent")

    def _create_generic_tool_schema(self, tool_name: str, tool: Any) -> Dict[str, Any]:
        """
        Create a generic tool schema that can be adapted by each provider

        Args:
            tool_name: Name of the tool
            tool: The tool instance

        Returns:
            Generic tool schema
        """
        parameters = {}
        required = []

        # Extract parameters from tool's args_schema if available
        if hasattr(tool, 'args_schema'):
            schema = tool.args_schema
            if hasattr(schema, '__fields__'):
                for field_name, field_info in schema.__fields__.items():
                    # Get field type
                    field_type = "string"  # Default
                    annotation = getattr(field_info, 'annotation', None) or getattr(field_info, 'type_', None)
                    if annotation:
                        if annotation == int:
                            field_type = "integer"
                        elif annotation == float:
                            field_type = "number"
                        elif annotation == bool:
                            field_type = "boolean"

                    # Get description
                    description = ""
                    if hasattr(field_info, 'field_info') and field_info.field_info:
                        description = field_info.field_info.description or ""
                    elif hasattr(field_info, 'description'):
                        description = field_info.description or ""

                    if not description:
                        description = f"Parameter {field_name}"

                    parameters[field_name] = {
                        "type": field_type,
                        "description": description
                    }

                    # Check if required
                    is_required = False
                    if hasattr(field_info, 'is_required') and callable(field_info.is_required):
                        is_required = field_info.is_required()
                    elif hasattr(field_info, 'required'):
                        is_required = field_info.required
                    elif hasattr(field_info, 'default') and field_info.default is None:
                        is_required = True

                    if is_required:
                        required.append(field_name)

        return {
            "name": tool_name,
            "description": tool.description or f"Tool {tool_name}",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required
            }
        }

    def convert_tools_for_provider(self, provider_type: str) -> List[Dict[str, Any]]:
        """
        Convert generic tool schemas to provider-specific format

        Args:
            provider_type: Type of provider (anthropic, openai, ollama)

        Returns:
            Tools in provider-specific format
        """
        if provider_type == "anthropic":
            # Anthropic format
            return [{
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"]
            } for tool in self.tool_schemas]

        elif provider_type == "openai":
            # OpenAI format (functions)
            return [{
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            } for tool in self.tool_schemas]

        else:
            # Default format (can be extended for other providers)
            return self.tool_schemas

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
            # Check if provider supports tool calling
            if not self.llm_provider.supports_function_calling():
                # Fallback to simple chat without tools
                response = await self.llm_provider.chat_completion([
                    {"role": "user", "content": message}
                ])
                return {
                    "content": response.get("content", ""),
                    "tool_calls": None,
                    "provider": self.llm_provider.__class__.__name__
                }

            # Determine provider type
            provider_type = self._get_provider_type()
            tools_formatted = self.convert_tools_for_provider(provider_type)

            # Log tool selection prompt
            logger.info("=" * 80)
            logger.info("🔧 [TOOL SELECTOR] Input Message:")
            logger.info("-" * 80)
            logger.info(f"Query: {message}")
            logger.info(f"Available tools: {len(tools_formatted)}")
            for tool in tools_formatted[:3]:  # Log first 3 tools
                tool_name = tool.get('name', tool.get('function', {}).get('name', 'unknown'))
                logger.info(f"  - {tool_name}")
            logger.info("=" * 80)

            # Get model from settings
            model = None
            try:
                from app.core.config import get_settings
                settings = get_settings()
                model = settings.get_model_for_agent("tool_selector")
                logger.info(f"🤖 [TOOL SELECTOR] Using model: {model}")
            except Exception as e:
                logger.debug(f"Could not get model from settings: {e}")

            # Detect if this is a list query
            query_lower = message.lower()
            is_list_query = any(keyword in query_lower for keyword in [
                "show me", "list", "which", "get all", "associated", "find all"
            ])

            # Build base system message based on query intent
            if is_list_query:
                base_system_content = (
                    "You are an analytical assistant. The user is requesting a LIST of records.\n\n"

                    "RESPONSE STRUCTURE:\n"
                    "1. Brief intro (1 line)\n"
                    "2. Data table (4-5 key columns, markdown format)\n"
                    "3. DATA-GROUNDED ANALYSIS (REQUIRED)\n\n"

                    "=== ANALYSIS FRAMEWORK ===\n\n"

                    "After presenting the table, provide analysis based ONLY on observable data:\n\n"

                    "A) STATISTICAL SUMMARY:\n"
                    "   - Calculate totals, percentages, ratios from visible data\n"
                    "   - Example: '6 out of 24 alerts (25%) are unassigned'\n"
                    "   - Example: 'Top 2 customers account for 10 alerts (42% of total)'\n\n"

                    "B) DISTRIBUTION PATTERNS:\n"
                    "   - Describe how values are spread across categories\n"
                    "   - Identify concentrations, clusters, or imbalances\n"
                    "   - Compare highest vs. lowest values\n"
                    "   - Example: 'Alert counts range from 1 to 6, with 60% having only 1 alert'\n\n"

                    "C) NOTABLE OBSERVATIONS:\n"
                    "   - Point out interesting patterns or contrasts in the data\n"
                    "   - Use neutral, factual language\n"
                    "   - Example: 'The unassigned category contains more alerts than any single customer'\n\n"

                    "=== STRICT RULES ===\n\n"

                    "DO:\n"
                    "✅ State exactly what the data shows\n"
                    "✅ Calculate percentages and ratios from visible data\n"
                    "✅ Compare values within the dataset\n"
                    "✅ Describe patterns objectively\n"
                    "✅ Use specific numbers from the data\n\n"

                    "DO NOT:\n"
                    "❌ Reference thresholds, SLAs, or benchmarks not in the data\n"
                    "❌ Claim something is 'too high/low' without visible criteria\n"
                    "❌ Make recommendations requiring unknown information\n"
                    "❌ Assume business rules, policies, or norms\n"
                    "❌ Use terms like 'risk', 'breach', 'concern' without factual basis\n"
                    "❌ Infer total system state from partial results\n"
                    "❌ Mention visualizations or formatting choices\n\n"

                    "EXAMPLE ANALYSIS:\n"
                    "```\n"
                    "ANALYSIS:\n"
                    "• Distribution: 6 alerts (25%) are unassigned, 18 alerts (75%) are distributed across 9 customers\n"
                    "• Concentration: Michele Parker and Jamie Ponce together account for 10 alerts (42% of total)\n"
                    "• Range: Alert counts per customer vary from 1 to 5\n"
                    "• Notable: The unassigned category has more alerts (6) than any individual assigned customer\n"
                    "```\n\n"

                    "Remember: Only analyze what you can directly observe in THIS query's results.\n"
                )
            else:
                base_system_content = (
                    "You are a helpful assistant. When responding to users:\n\n"
                    "1. Format responses with proper markdown:\n"
                    "   - Use numbered lists (1., 2., 3.) for sequential items\n"
                    "   - Use bullet points (-, *) for unordered lists\n"
                    "   - Add blank lines between paragraphs\n"
                    "   - Add blank lines between list items for readability\n\n"
                    "2. Present data clearly and professionally\n"
                    "3. Use proper spacing and formatting for better readability\n\n"
                    "Always ensure your responses are well-formatted and easy to read."
                )

            # Enhance with visualization instructions if enabled
            enable_visualizations = False
            try:
                from app.core.config import get_settings
                settings = get_settings()
                enable_visualizations = getattr(settings, 'enable_visualizations', False)

                if enable_visualizations:
                    try:
                        from app.prompts.visualization_prompt import VisualizationPromptBuilder
                        viz_builder = VisualizationPromptBuilder()
                        base_system_content = viz_builder.build_enhanced_prompt(
                            base_prompt=base_system_content,
                            context={'query': message}
                        )
                        logger.info("✨ [TOOL SELECTOR] Enhanced prompt with visualization instructions")
                    except Exception as e:
                        logger.warning(f"Failed to enhance prompt with visualization: {e}")
            except Exception as e:
                logger.debug(f"Could not check visualization settings: {e}")

            # Initial call with tools
            messages = [{"role": "system", "content": base_system_content}]

            # Retrieve conversation history if available
            logger.info(f"🔍 DEBUG: session_manager={self.session_manager is not None}, session_id={session_id}")
            if self.session_manager and session_id:
                try:
                    history = await self.session_manager.get_history(session_id)
                    logger.info(f"📚 Retrieved {len(history)} messages from conversation history")
                    logger.info(f"📚 History content: {history}")
                    for msg in history:
                        messages.append({
                            "role": msg.get("role"),
                            "content": msg.get("content")
                        })
                except Exception as e:
                    logger.warning(f"Failed to retrieve conversation history: {e}", exc_info=True)
            else:
                logger.warning(f"⚠️ NOT retrieving history - session_manager: {self.session_manager is not None}, session_id: {session_id}")

            # Add current message
            messages.append({"role": "user", "content": message})
            logger.info(f"📝 Total messages in context: {len(messages)} (including system prompt)")

            # Prepare kwargs for model parameter
            tool_kwargs = {}
            if model:
                tool_kwargs["model"] = model

            response = await self.llm_provider.chat_completion_with_tools(
                messages=messages,
                tools=tools_formatted,
                **tool_kwargs
            )

            # Check for tool calls in response
            tool_calls = self._extract_tool_calls(response, provider_type)

            # Log tool selection response
            logger.info("=" * 80)
            logger.info("🔧 [TOOL SELECTOR] Response:")
            logger.info("-" * 80)
            if tool_calls:
                for tc in tool_calls:
                    logger.info(f"  Tool: {tc.get('name')}")
                    logger.info(f"  Args: {json.dumps(tc.get('arguments', {}), indent=2)}")
            else:
                logger.info("  No tools called")
            logger.info("=" * 80)

            if tool_calls:
                # Execute tools
                tool_results = await self._execute_tools(tool_calls)

                # Format messages for follow-up based on provider
                if provider_type == "anthropic":
                    # Anthropic format - ensure content is properly formatted
                    assistant_content = response.get("content")

                    # Add the assistant's response with tool_use blocks
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content if isinstance(assistant_content, list) else []
                    })

                    # Format tool results as proper tool_result blocks
                    tool_result_content = []
                    for i, (tool_call, result) in enumerate(zip(tool_calls, tool_results if isinstance(tool_results, list) else [tool_results])):
                        tool_result_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.get("id"),
                            "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        })

                    messages.append({
                        "role": "user",
                        "content": tool_result_content
                    })
                elif provider_type == "openai":
                    # OpenAI format
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": tool_calls
                    })
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(tool_results),
                        "tool_call_id": tool_calls[0].get("id") if tool_calls else None
                    })
                else:
                    # Generic format
                    messages.append({
                        "role": "assistant",
                        "content": str(response)
                    })
                    messages.append({
                        "role": "system",
                        "content": f"Tool results: {json.dumps(tool_results)}"
                    })

                # Log response formatter prompt
                logger.info("=" * 80)
                logger.info("✨ [RESPONSE FORMATTER] Input:")
                logger.info("-" * 80)
                logger.info(f"Original query: {message}")
                logger.info(f"Tool results available: {len(tool_results) if isinstance(tool_results, list) else 1} result(s)")
                logger.info(f"Message history length: {len(messages)}")
                # Log last message (tool results) preview
                if messages:
                    last_msg = messages[-1]
                    logger.info(f"Last message role: {last_msg.get('role')}")
                    if last_msg.get('role') == 'user' and isinstance(last_msg.get('content'), list):
                        for block in last_msg.get('content', [])[:2]:  # Log first 2 blocks
                            if block.get('type') == 'tool_result':
                                content = block.get('content', '')
                                logger.info(f"  Tool result preview: {content[:200]}...")
                logger.info("=" * 80)

                # Get model from settings for response formatting
                formatter_model = None
                try:
                    from app.core.config import get_settings
                    settings = get_settings()
                    formatter_model = settings.get_model_for_agent("response_formatter")
                    logger.info(f"🤖 [RESPONSE FORMATTER] Using model: {formatter_model}")
                except Exception as e:
                    logger.debug(f"Could not get model from settings: {e}")

                # Prepare kwargs for model parameter
                formatter_kwargs = {}
                if formatter_model:
                    formatter_kwargs["model"] = formatter_model

                # Get final response
                final_response = await self.llm_provider.chat_completion_with_tools(
                    messages=messages,
                    tools=tools_formatted,
                    **formatter_kwargs
                )

                content = self._extract_content(final_response, provider_type)

                # Log response formatter output
                logger.info("=" * 80)
                logger.info("✨ [RESPONSE FORMATTER] Response:")
                logger.info("-" * 80)
                logger.info(content[:500] + ("..." if len(content) > 500 else ""))
                logger.info("=" * 80)

                return {
                    "content": content,
                    "tool_calls": tool_results,
                    "provider": self.llm_provider.__class__.__name__
                }
            else:
                # No tools called
                return {
                    "content": self._extract_content(response, provider_type),
                    "tool_calls": None,
                    "provider": self.llm_provider.__class__.__name__
                }

        except Exception as e:
            logger.error(f"Error in universal agent: {e}")
            return {
                "content": f"Error processing request: {str(e)}",
                "tool_calls": None,
                "error": str(e),
                "provider": self.llm_provider.__class__.__name__
            }

    async def process_message_streaming(
        self,
        message: str,
        session_id: Optional[str] = None
    ):
        """
        Process message with streaming for final response ONLY.

        This method:
        1. Uses blocking calls for tool selection (needs structured response)
        2. Executes tools
        3. STREAMS the final user-facing response

        Yields:
            String chunks of the final response
        """
        try:
            # Check if provider supports tool calling
            if not self.llm_provider.supports_function_calling():
                # Fallback to simple streaming
                async for chunk in self.llm_provider.stream_completion(
                    messages=[{"role": "user", "content": message}]
                ):
                    if chunk.get("content"):
                        yield chunk.get("content")
                return

            provider_type = self._get_provider_type()
            tools_formatted = self.convert_tools_for_provider(provider_type)

            # 🔒 BLOCKING: Tool selection (needs structured response)
            logger.info("🔧 [TOOL SELECTOR] Selecting tool (blocking)...")

            # Get model for tool selector
            model_selector = None
            try:
                from app.core.config import get_settings
                settings = get_settings()
                model_selector = settings.get_model_for_agent("tool_selector")
                logger.info(f"🤖 [TOOL SELECTOR] Using model: {model_selector}")
            except:
                pass

            # Prepare kwargs
            tool_kwargs = {}
            if model_selector:
                tool_kwargs["model"] = model_selector

            # Detect if this is a list query
            query_lower = message.lower()
            is_list_query = any(keyword in query_lower for keyword in [
                "show me", "list", "which", "get all", "associated", "find all"
            ])

            # Build base system message based on query intent
            if is_list_query:
                base_system_content = (
                    "You are an analytical assistant. The user is requesting a LIST of records.\n\n"

                    "RESPONSE STRUCTURE:\n"
                    "1. Brief intro (1 line)\n"
                    "2. Data table (4-5 key columns, markdown format)\n"
                    "3. DATA-GROUNDED ANALYSIS (REQUIRED)\n\n"

                    "=== ANALYSIS FRAMEWORK ===\n\n"

                    "After presenting the table, provide analysis based ONLY on observable data:\n\n"

                    "A) STATISTICAL SUMMARY:\n"
                    "   - Calculate totals, percentages, ratios from visible data\n"
                    "   - Example: '6 out of 24 alerts (25%) are unassigned'\n"
                    "   - Example: 'Top 2 customers account for 10 alerts (42% of total)'\n\n"

                    "B) DISTRIBUTION PATTERNS:\n"
                    "   - Describe how values are spread across categories\n"
                    "   - Identify concentrations, clusters, or imbalances\n"
                    "   - Compare highest vs. lowest values\n"
                    "   - Example: 'Alert counts range from 1 to 6, with 60% having only 1 alert'\n\n"

                    "C) NOTABLE OBSERVATIONS:\n"
                    "   - Point out interesting patterns or contrasts in the data\n"
                    "   - Use neutral, factual language\n"
                    "   - Example: 'The unassigned category contains more alerts than any single customer'\n\n"

                    "=== STRICT RULES ===\n\n"

                    "DO:\n"
                    "✅ State exactly what the data shows\n"
                    "✅ Calculate percentages and ratios from visible data\n"
                    "✅ Compare values within the dataset\n"
                    "✅ Describe patterns objectively\n"
                    "✅ Use specific numbers from the data\n\n"

                    "DO NOT:\n"
                    "❌ Reference thresholds, SLAs, or benchmarks not in the data\n"
                    "❌ Claim something is 'too high/low' without visible criteria\n"
                    "❌ Make recommendations requiring unknown information\n"
                    "❌ Assume business rules, policies, or norms\n"
                    "❌ Use terms like 'risk', 'breach', 'concern' without factual basis\n"
                    "❌ Infer total system state from partial results\n"
                    "❌ Mention visualizations or formatting choices\n\n"

                    "EXAMPLE ANALYSIS:\n"
                    "```\n"
                    "ANALYSIS:\n"
                    "• Distribution: 6 alerts (25%) are unassigned, 18 alerts (75%) are distributed across 9 customers\n"
                    "• Concentration: Michele Parker and Jamie Ponce together account for 10 alerts (42% of total)\n"
                    "• Range: Alert counts per customer vary from 1 to 5\n"
                    "• Notable: The unassigned category has more alerts (6) than any individual assigned customer\n"
                    "```\n\n"

                    "Remember: Only analyze what you can directly observe in THIS query's results.\n"
                )
            else:
                base_system_content = (
                    "You are a helpful assistant. When responding to users:\n\n"
                    "1. Format responses with proper markdown:\n"
                    "   - Use numbered lists (1., 2., 3.) for sequential items\n"
                    "   - Use bullet points (-, *) for unordered lists\n"
                    "   - Add blank lines between paragraphs\n"
                    "   - Add blank lines between list items for readability\n\n"
                    "2. Present data clearly and professionally\n"
                    "3. Use proper spacing and formatting for better readability\n\n"
                    "Always ensure your responses are well-formatted and easy to read."
                )

            # Enhance with visualization instructions if enabled
            try:
                from app.core.config import get_settings
                settings = get_settings()
                enable_visualizations = getattr(settings, 'enable_visualizations', False)

                if enable_visualizations:
                    try:
                        from app.prompts.visualization_prompt import VisualizationPromptBuilder
                        viz_builder = VisualizationPromptBuilder()
                        base_system_content = viz_builder.build_enhanced_prompt(
                            base_prompt=base_system_content,
                            context={'query': message}
                        )
                        logger.info("✨ [TOOL SELECTOR] Enhanced prompt with visualization instructions")
                    except Exception as e:
                        logger.warning(f"Failed to enhance prompt with visualization: {e}")
            except Exception as e:
                logger.debug(f"Could not check visualization settings: {e}")

            messages = [{"role": "system", "content": base_system_content}]

            # Retrieve conversation history if available
            if self.session_manager and session_id:
                try:
                    history = await self.session_manager.get_history(session_id)
                    logger.info(f"📚 [STREAMING] Retrieved {len(history)} messages from conversation history")
                    for msg in history:
                        messages.append({
                            "role": msg.get("role"),
                            "content": msg.get("content")
                        })
                except Exception as e:
                    logger.warning(f"Failed to retrieve conversation history: {e}")

            # Add current message
            messages.append({"role": "user", "content": message})

            response = await self.llm_provider.chat_completion_with_tools(
                messages=messages,
                tools=tools_formatted,
                **tool_kwargs
            )

            # Extract and execute tool calls
            tool_calls = self._extract_tool_calls(response, provider_type)

            if tool_calls:
                # 🔒 BLOCKING: Execute tools
                logger.info(f"⚙️ Executing {len(tool_calls)} tool(s)...")
                tool_results = await self._execute_tools(tool_calls)

                # Format messages for final response
                if provider_type == "anthropic":
                    assistant_content = response.get("content")
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content if isinstance(assistant_content, list) else []
                    })

                    tool_result_content = []
                    for tool_call, result in zip(tool_calls, tool_results if isinstance(tool_results, list) else [tool_results]):
                        tool_result_content.append({
                            "type": "tool_result",
                            "tool_use_id": tool_call.get("id"),
                            "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                        })

                    messages.append({
                        "role": "user",
                        "content": tool_result_content
                    })
                elif provider_type == "openai":
                    messages.append({
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": tool_calls
                    })
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(tool_results),
                        "tool_call_id": tool_calls[0].get("id") if tool_calls else None
                    })
                else:
                    messages.append({
                        "role": "assistant",
                        "content": str(response)
                    })
                    messages.append({
                        "role": "system",
                        "content": f"Tool results: {json.dumps(tool_results)}"
                    })

                # 🌊 STREAMING: Get final response WITHOUT tools
                # Use StreamingHelper for provider-agnostic streaming
                logger.info("🌊 [RESPONSE FORMATTER] Streaming final response...")

                # Get model for response formatter
                model_formatter = None
                try:
                    from app.core.config import get_settings
                    settings = get_settings()
                    model_formatter = settings.get_model_for_agent("response_formatter")
                    logger.info(f"🤖 [RESPONSE FORMATTER] Using model: {model_formatter}")
                except:
                    pass

                # Prepare kwargs
                formatter_kwargs = {}
                if model_formatter:
                    formatter_kwargs["model"] = model_formatter

                # Use StreamingHelper - works with ALL providers
                # This ensures tools are NOT passed to response formatting step
                try:
                    async for chunk in StreamingHelper.stream_response_without_tools(
                        provider=self.llm_provider,
                        messages=messages,
                        **formatter_kwargs
                    ):
                        yield chunk
                except NotImplementedError as e:
                    # Provider doesn't implement required interface
                    logger.error(f"Provider incompatible: {e}")
                    yield f"Error: {str(e)}"

            else:
                # No tools called - stream direct response
                content = self._extract_content(response, provider_type)
                yield content

        except Exception as e:
            logger.error(f"Error in streaming universal agent: {e}")
            yield f"Error processing request: {str(e)}"

    def _get_provider_type(self) -> str:
        """Determine the provider type from the class name"""
        class_name = self.llm_provider.__class__.__name__.lower()
        if "anthropic" in class_name:
            return "anthropic"
        elif "openai" in class_name:
            return "openai"
        elif "ollama" in class_name:
            return "ollama"
        else:
            return "generic"

    def _extract_tool_calls(self, response: Dict, provider_type: str) -> List[Dict]:
        """Extract tool calls from provider response"""
        if provider_type == "anthropic":
            # Anthropic format
            content = response.get("content", [])
            tool_calls = []
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        tool_calls.append({
                            "name": item.get("name"),
                            "arguments": item.get("input", {}),
                            "id": item.get("id")
                        })
            return tool_calls

        elif provider_type == "openai":
            # OpenAI format
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                tool_calls = message.get("tool_calls", [])
                return [{
                    "name": tc.get("function", {}).get("name"),
                    "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
                    "id": tc.get("id")
                } for tc in tool_calls]

        return []

    def _extract_content(self, response: Dict, provider_type: str) -> str:
        """Extract text content from provider response"""
        if provider_type == "anthropic":
            content = response.get("content", [])
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                return " ".join(text_parts)

        elif provider_type == "openai":
            choices = response.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")

        # Generic fallback
        return response.get("content", str(response))

    async def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tool calls"""
        results = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
            tool_id = tool_call.get("id")

            logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

            if tool_name in self.tools:
                try:
                    tool = self.tools[tool_name]

                    # Execute tool
                    if hasattr(tool, '_arun'):
                        result = await tool._arun(**tool_args)
                    elif hasattr(tool, '_run'):
                        result = tool._run(**tool_args)
                    else:
                        result = f"Tool {tool_name} has no executable method"

                    logger.info(f"Tool {tool_name} returned: {str(result)[:200]}...")

                    results.append({
                        "tool": tool_name,
                        "result": str(result),
                        "id": tool_id
                    })

                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_name}: {e}")
                    results.append({
                        "tool": tool_name,
                        "error": str(e),
                        "id": tool_id
                    })
            else:
                logger.warning(f"Tool {tool_name} not found")
                results.append({
                    "tool": tool_name,
                    "error": f"Tool {tool_name} not found",
                    "id": tool_id
                })

        return results

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())

    def get_tool_descriptions(self) -> List[str]:
        """Get descriptions of all available tools"""
        descriptions = []
        for tool_name, tool in self.tools.items():
            descriptions.append(f"- {tool_name}: {tool.description}")
        return descriptions