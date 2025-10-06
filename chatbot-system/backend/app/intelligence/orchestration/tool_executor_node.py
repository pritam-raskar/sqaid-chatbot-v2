"""
Tool Executor Node - Executes tools using UniversalAgent.

This node is used when specialized agents are not registered.
It leverages the UniversalAgent to execute tools from the tool registry.
"""
import logging
from typing import Dict, Any, Optional
from app.intelligence.orchestration.base_node import BaseNode
from app.intelligence.orchestration.state import StateHelper
from app.intelligence.orchestration.types import AgentType, AgentState, NodeResponse

logger = logging.getLogger(__name__)


class ToolExecutorNode(BaseNode):
    """
    Node that executes tools using UniversalAgent.

    Used as fallback when specialized agents are not registered.
    Leverages UniversalAgent for intelligent tool selection and execution.
    """

    def __init__(
        self,
        node_name: str,
        agent_type: AgentType,
        tool_registry,
        llm_provider,
        session_manager=None
    ):
        """
        Initialize ToolExecutorNode.

        Args:
            node_name: Name of the node
            agent_type: Type of agent this node represents
            tool_registry: Tool registry instance
            llm_provider: LLM provider instance
            session_manager: Optional SessionManager for conversation history
        """
        super().__init__(node_name=node_name, agent_type=agent_type)
        self.tool_registry = tool_registry
        self.llm_provider = llm_provider
        self.session_manager = session_manager

        # Initialize UniversalAgent for tool execution
        from app.intelligence.universal_agent import UniversalAgent
        self.universal_agent = UniversalAgent(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            session_manager=session_manager
        )

        logger.info(f"✅ ToolExecutorNode '{node_name}' initialized with UniversalAgent")

    async def _execute(self, state: AgentState) -> NodeResponse:
        """
        Execute tools using UniversalAgent with optional streaming.

        Args:
            state: Current AgentState

        Returns:
            NodeResponse with results and updated state
        """
        query = state["user_query"]

        self._log(f"Executing query using UniversalAgent: {query[:100]}...")

        try:
            # Check if streaming is enabled
            enable_streaming = False
            try:
                from app.core.config import get_settings
                settings = get_settings()
                enable_streaming = settings.enable_llm_streaming
            except:
                pass

            if enable_streaming and hasattr(self.universal_agent, 'process_message_streaming'):
                # 🌊 STREAMING MODE
                self._log("🌊 Using streaming mode for response formatting")

                full_content = ""
                tool_calls = []

                async for chunk in self.universal_agent.process_message_streaming(
                    message=query,
                    session_id=state.get("session_id", "default")
                ):
                    full_content += chunk
                    # TODO: Stream chunks to WebSocket if available in the future

                # Build response data
                response_data = {
                    "content": full_content,
                    "tool_calls": tool_calls,
                    "tool_count": len(tool_calls),
                    "streamed": True
                }

            else:
                # 🔒 BLOCKING MODE (original behavior)
                self._log("📦 Using blocking mode")

                result = await self.universal_agent.process_message(
                    message=query,
                    session_id=state.get("session_id", "default")
                )

                content = result.get("content", "")
                tool_calls = result.get("tool_calls", [])

                self._log(f"UniversalAgent executed {len(tool_calls)} tool(s)")

                response_data = {
                    "content": content,
                    "tool_calls": tool_calls,
                    "tool_count": len(tool_calls),
                    "streamed": False
                }

            # Add result to state
            state_update = StateHelper.add_agent_result(
                state,
                agent_type=self.agent_type,
                result_data=response_data,
                tool_name=response_data.get("tool_calls", [{}])[0].get("tool", "none") if response_data.get("tool_calls") else "none",
                execution_time_ms=0,
                error=None
            )

            # Mark step complete
            state_update.update(StateHelper.mark_step_complete(state, success=True))

            # Add final response
            if response_data.get("content"):
                state_update["final_response"] = response_data["content"]

            return state_update

        except Exception as e:
            self._log(f"Error executing tools: {e}", level="error")

            # Return error state
            error_msg = f"Tool execution failed: {str(e)}"
            state_update = StateHelper.add_agent_result(
                state,
                agent_type=self.agent_type,
                result_data={"error": error_msg},
                tool_name="error",
                execution_time_ms=0,
                error=error_msg
            )

            state_update.update(StateHelper.mark_step_complete(state, success=False))
            state_update["final_response"] = f"Sorry, I encountered an error: {error_msg}"

            return state_update
