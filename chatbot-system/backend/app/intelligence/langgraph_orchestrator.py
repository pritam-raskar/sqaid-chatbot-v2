"""
LangGraph Orchestrator - Main orchestrator for multi-agent workflows.
Replaces UniversalAgent when USE_LANGGRAPH feature flag is enabled.
"""
import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
import json
from datetime import datetime

from app.intelligence.orchestration.types import AgentState
from app.intelligence.orchestration.state import StateFactory
from app.intelligence.orchestration.execution_planner import ExecutionPlanner
from app.intelligence.orchestration.supervisor_node import SupervisorNode
from app.intelligence.orchestration.workflow import WorkflowBuilder
from app.intelligence.agents.agent_registry import AgentRegistry
from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.core.config import AppSettings

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """
    Main orchestrator for LangGraph multi-agent workflows.

    Capabilities:
    - Multi-agent orchestration with supervisor pattern
    - Intelligent query planning and routing
    - Cross-source data consolidation
    - Streaming response support
    - Compatible with all LLM providers (Anthropic, OpenAI, Eliza, LiteLLM)

    This class provides the same interface as UniversalAgent for
    seamless migration.
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        agent_registry: Optional[AgentRegistry] = None,
        settings: Optional[AppSettings] = None,
        session_manager=None
    ):
        """
        Initialize LangGraph orchestrator.

        Args:
            llm_provider: LLM provider (supports all providers)
            tool_registry: Tool registry with all available tools
            agent_registry: Optional agent registry (creates if not provided)
            settings: Optional app settings
            session_manager: Optional SessionManager for conversation history

        Example:
            orchestrator = LangGraphOrchestrator(
                llm_provider=anthropic_provider,
                tool_registry=tool_registry
            )
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry or AgentRegistry()
        self.settings = settings
        self.session_manager = session_manager

        logger.info("🚀 Initializing LangGraph Orchestrator...")

        # Create execution planner
        logger.info("  📋 Creating execution planner...")
        self.execution_planner = ExecutionPlanner(llm_provider, tool_registry)

        # Create supervisor node
        logger.info("  👔 Creating supervisor node...")
        self.supervisor_node = SupervisorNode(self.execution_planner)

        # Build workflow
        logger.info("  🔧 Building LangGraph workflow...")
        self.workflow_builder = WorkflowBuilder(
            supervisor_node=self.supervisor_node,
            agent_registry=self.agent_registry,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            session_manager=session_manager
        )

        # Compile workflow
        logger.info("  ⚙️ Compiling StateGraph...")
        self.workflow = self.workflow_builder.build()

        logger.info("✅ LangGraph Orchestrator initialized successfully")

    async def process_message(
        self,
        message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Process a user message through the LangGraph workflow.

        Args:
            message: User query
            session_id: Session identifier
            context: Optional context (page state, filters, etc.)
            stream: Whether to stream response (for WebSocket)

        Returns:
            Response dictionary with content and metadata

        Example:
            response = await orchestrator.process_message(
                message="Get all high severity alerts",
                session_id="session-123",
                stream=False
            )
        """
        logger.info(f"📨 Processing message: {message[:50]}...")

        try:
            # Create initial state
            initial_state = StateFactory.create_initial_state(
                user_query=message,
                session_id=session_id,
                context=context
            )

            logger.info(f"🎯 Created initial state for session {session_id}")

            # Execute workflow
            if stream:
                # Streaming mode for WebSocket
                return await self._execute_workflow_streaming(initial_state, session_id)
            else:
                # Non-streaming mode
                return await self._execute_workflow(initial_state, session_id)

        except Exception as e:
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            return {
                "success": False,
                "content": f"Error processing query: {str(e)}",
                "error": str(e),
                "metadata": {
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    async def _execute_workflow(
        self,
        initial_state: AgentState,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute workflow in non-streaming mode.

        Args:
            initial_state: Initial AgentState
            session_id: Session ID

        Returns:
            Response dictionary
        """
        logger.info("▶️ Executing workflow (non-streaming)...")

        try:
            # Invoke workflow
            final_state = await self.workflow.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": session_id}}
            )

            logger.info("✅ Workflow execution complete")

            # Extract response
            final_response = final_state.get("final_response", "")
            execution_plan = final_state.get("execution_plan", {})

            # Collect metadata
            metadata = {
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "steps_executed": len(execution_plan.get("steps", [])),
                "complexity": execution_plan.get("estimated_complexity", "unknown"),
                "sql_results_count": len(final_state.get("sql_results", [])),
                "api_results_count": len(final_state.get("api_results", [])),
                "soap_results_count": len(final_state.get("soap_results", [])),
            }

            return {
                "success": True,
                "content": final_response,
                "metadata": metadata,
                "execution_plan": execution_plan
            }

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}", exc_info=True)
            raise

    async def _execute_workflow_streaming(
        self,
        initial_state: AgentState,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute workflow in streaming mode.

        Args:
            initial_state: Initial AgentState
            session_id: Session ID

        Returns:
            Response dictionary with streaming info

        Note: Actual streaming happens via astream() which returns
        AsyncGenerator. This method returns metadata about the stream.
        """
        logger.info("▶️ Executing workflow (streaming)...")

        try:
            # For streaming, we return a generator
            # The WebSocket handler will iterate over it
            stream_generator = self.workflow.astream(
                initial_state,
                config={"configurable": {"thread_id": session_id}}
            )

            return {
                "success": True,
                "streaming": True,
                "stream": stream_generator,
                "metadata": {
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        except Exception as e:
            logger.error(f"❌ Workflow streaming failed: {e}", exc_info=True)
            raise

    async def stream_workflow(
        self,
        message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream workflow execution events.

        Args:
            message: User query
            session_id: Session identifier
            context: Optional context

        Yields:
            Event dictionaries from workflow execution

        Example:
            async for event in orchestrator.stream_workflow(query, session_id):
                print(f"Event: {event['type']}")
                if event['type'] == 'node_complete':
                    print(f"Node {event['node']} completed")
        """
        logger.info(f"📡 Starting workflow stream for: {message[:50]}...")

        # Create initial state
        initial_state = StateFactory.create_initial_state(
            user_query=message,
            session_id=session_id,
            context=context
        )

        try:
            # Stream workflow events
            async for event in self.workflow.astream(
                initial_state,
                config={"configurable": {"thread_id": session_id}}
            ):
                # Event format from LangGraph:
                # {node_name: {state_updates}}

                for node_name, state_update in event.items():
                    yield {
                        "type": "node_update",
                        "node": node_name,
                        "state_update": state_update,
                        "timestamp": datetime.utcnow().isoformat()
                    }

            logger.info("✅ Workflow stream complete")

            # Final event
            yield {
                "type": "stream_complete",
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Workflow stream error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names.

        Returns:
            List of tool names

        Note: For compatibility with UniversalAgent interface
        """
        return [
            tool.name
            for tool in self.tool_registry.get_all_tools()
        ]

    def get_tool_descriptions(self) -> List[str]:
        """
        Get descriptions of all available tools.

        Returns:
            List of tool descriptions

        Note: For compatibility with UniversalAgent interface
        """
        descriptions = []
        for tool in self.tool_registry.get_all_tools():
            metadata = tool.metadata or {}
            desc = f"{tool.name}: {metadata.get('description', 'No description')}"
            descriptions.append(desc)
        return descriptions

    def get_workflow_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current workflow state for a session.

        Args:
            session_id: Session identifier

        Returns:
            Current state or None if not found

        Note: Requires checkpointing to be enabled
        """
        try:
            # LangGraph checkpointing allows state retrieval
            # This is a placeholder - actual implementation depends on
            # checkpointer configuration
            logger.info(f"📊 Getting workflow state for session {session_id}")
            return None  # TODO: Implement with checkpointer API
        except Exception as e:
            logger.error(f"❌ Error getting workflow state: {e}")
            return None

    def register_agent(self, agent_type: str, agent: Any) -> None:
        """
        Register a specialized agent.

        Args:
            agent_type: Type of agent (SQL, API, SOAP, etc.)
            agent: Agent instance

        Example:
            orchestrator.register_agent(AgentType.SQL_AGENT, sql_agent)
        """
        from app.intelligence.orchestration.types import AgentType

        # Convert string to AgentType enum if needed
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)

        self.agent_registry.register(agent_type, agent)
        logger.info(f"✅ Registered agent: {agent_type.value}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics.

        Returns:
            Statistics dictionary with agent counts, tool counts, etc.
        """
        return {
            "agents_registered": len(self.agent_registry.list_agents()),
            "tools_available": len(self.get_available_tools()),
            "workflow_compiled": self.workflow is not None,
            "provider": self.llm_provider.__class__.__name__,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def health_check(self) -> bool:
        """
        Check if orchestrator is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check LLM provider
            if not await self.llm_provider.health_check():
                logger.warning("⚠️ LLM provider health check failed")
                return False

            # Check workflow
            if not self.workflow:
                logger.warning("⚠️ Workflow not compiled")
                return False

            logger.info("✅ Orchestrator health check passed")
            return True

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"LangGraphOrchestrator("
            f"provider={self.llm_provider.__class__.__name__}, "
            f"agents={len(self.agent_registry.list_agents())}, "
            f"tools={len(self.get_available_tools())}"
            f")"
        )
