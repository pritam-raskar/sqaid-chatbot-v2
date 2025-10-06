"""
Workflow Builder - Constructs LangGraph StateGraph for multi-agent orchestration.
"""
import logging
from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.intelligence.orchestration.types import AgentState, AgentType
from app.intelligence.orchestration.supervisor_node import SupervisorNode
from app.intelligence.orchestration.consolidator_node import ConsolidatorNode
from app.intelligence.orchestration.routing import route_from_supervisor, route_from_agent
from app.intelligence.orchestration.base_node import BaseNode, PassthroughNode
from app.intelligence.agents.agent_registry import AgentRegistry
from app.intelligence.orchestration.state import StateHelper
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class WorkflowBuilder:
    """
    Builds LangGraph StateGraph workflow for multi-agent orchestration.

    Responsibilities:
    - Create StateGraph with AgentState
    - Add all nodes (supervisor, agents, consolidator)
    - Configure routing between nodes
    - Set entry point
    - Compile workflow with checkpointing
    """

    def __init__(
        self,
        supervisor_node: SupervisorNode,
        agent_registry: AgentRegistry,
        llm_provider: BaseLLMProvider,
        tool_registry=None,
        session_manager=None
    ):
        """
        Initialize workflow builder.

        Args:
            supervisor_node: SupervisorNode instance
            agent_registry: AgentRegistry with all agents
            llm_provider: LLM provider for consolidator (supports all providers)
            tool_registry: Tool registry for ToolExecutorNode fallback
            session_manager: Optional SessionManager for conversation history
        """
        self.supervisor_node = supervisor_node
        self.agent_registry = agent_registry
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.session_manager = session_manager

        logger.info("🔧 WorkflowBuilder initialized")

    def build(self) -> StateGraph:
        """
        Build and compile the LangGraph StateGraph.

        Returns:
            Compiled StateGraph ready for execution

        Architecture:
            START → supervisor → [sql_agent | api_agent | soap_agent] → supervisor → ... → consolidator → END
        """
        logger.info("🏗️ Building LangGraph StateGraph...")

        # Create StateGraph
        workflow = StateGraph(AgentState)

        # Add supervisor node
        logger.info("  ➕ Adding supervisor node...")
        async def supervisor_fn(state): return await self.supervisor_node(state)
        workflow.add_node("supervisor", supervisor_fn)

        # Add agent nodes
        logger.info("  ➕ Adding agent nodes...")
        sql_agent_node = self._create_sql_agent_node()
        async def sql_agent_fn(state): return await sql_agent_node(state)
        workflow.add_node("sql_agent", sql_agent_fn)

        api_agent_node = self._create_api_agent_node()
        async def api_agent_fn(state): return await api_agent_node(state)
        workflow.add_node("api_agent", api_agent_fn)

        soap_agent_node = self._create_soap_agent_node()
        async def soap_agent_fn(state): return await soap_agent_node(state)
        workflow.add_node("soap_agent", soap_agent_fn)

        # Add consolidator node (Phase 4)
        logger.info("  ➕ Adding consolidator node...")
        consolidator_node = self._create_consolidator_node()
        async def consolidator_fn(state): return await consolidator_node(state)
        workflow.add_node("consolidator", consolidator_fn)

        # Set entry point
        logger.info("  🚪 Setting entry point to supervisor...")
        workflow.set_entry_point("supervisor")

        # Configure routing from supervisor
        logger.info("  🔀 Configuring routing from supervisor...")
        workflow.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            {
                "sql_agent": "sql_agent",
                "api_agent": "api_agent",
                "soap_agent": "soap_agent",
                "consolidator": "consolidator",
                "end": END
            }
        )

        # Configure routing from agents back to supervisor
        logger.info("  🔀 Configuring routing from agents...")
        workflow.add_conditional_edges("sql_agent", route_from_agent, {"supervisor": "supervisor", "end": END})
        workflow.add_conditional_edges("api_agent", route_from_agent, {"supervisor": "supervisor", "end": END})
        workflow.add_conditional_edges("soap_agent", route_from_agent, {"supervisor": "supervisor", "end": END})

        # Consolidator always ends
        workflow.add_edge("consolidator", END)

        # Compile workflow
        logger.info("  ⚙️ Compiling workflow with checkpointing...")
        compiled = workflow.compile(checkpointer=MemorySaver())

        logger.info("✅ StateGraph built and compiled successfully")

        return compiled

    def _create_sql_agent_node(self) -> BaseNode:
        """Create node function for SQL Agent."""
        sql_agent = self.agent_registry.get_agent(AgentType.SQL_AGENT)

        if not sql_agent:
            logger.warning("⚠️ SQL Agent not registered, using ToolExecutorNode")
            # Create a node that executes tools from tool registry
            from .tool_executor_node import ToolExecutorNode
            return ToolExecutorNode(
                node_name="sql_agent",
                agent_type=AgentType.SQL_AGENT,
                tool_registry=self.tool_registry,
                llm_provider=self.llm_provider,
                session_manager=self.session_manager
            )

        # Create wrapper node
        class SQLAgentNode(BaseNode):
            def __init__(self, agent):
                super().__init__(node_name="sql_agent", agent_type=AgentType.SQL_AGENT)
                self.agent = agent

            async def _execute(self, state: AgentState) -> dict:
                query = state["user_query"]

                # Get current step parameters if available
                current_step = StateHelper.get_current_step(state)
                parameters = current_step["parameters"] if current_step else {}

                # Execute agent
                result = await self.agent.execute(
                    query=query,
                    context=state.get("context"),
                    parameters=parameters
                )

                # Add result to state
                response = StateHelper.add_agent_result(
                    state,
                    agent_type=AgentType.SQL_AGENT,
                    result_data=result["data"],
                    tool_name=result["tool_name"],
                    execution_time_ms=result["execution_time_ms"],
                    error=result["error"]
                )

                # Mark step complete and increment
                response.update(StateHelper.mark_step_complete(state, success=result["error"] is None))

                return response

        return SQLAgentNode(sql_agent)

    def _create_api_agent_node(self) -> BaseNode:
        """Create node function for API Agent."""
        api_agent = self.agent_registry.get_agent(AgentType.API_AGENT)

        if not api_agent:
            logger.warning("⚠️ API Agent not registered, using ToolExecutorNode")
            from .tool_executor_node import ToolExecutorNode
            return ToolExecutorNode(
                node_name="api_agent",
                agent_type=AgentType.API_AGENT,
                tool_registry=self.tool_registry,
                llm_provider=self.llm_provider,
                session_manager=self.session_manager
            )

        class APIAgentNode(BaseNode):
            def __init__(self, agent):
                super().__init__(node_name="api_agent", agent_type=AgentType.API_AGENT)
                self.agent = agent

            async def _execute(self, state: AgentState) -> dict:
                query = state["user_query"]
                current_step = StateHelper.get_current_step(state)
                parameters = current_step["parameters"] if current_step else {}

                result = await self.agent.execute(
                    query=query,
                    context=state.get("context"),
                    parameters=parameters
                )

                response = StateHelper.add_agent_result(
                    state,
                    agent_type=AgentType.API_AGENT,
                    result_data=result["data"],
                    tool_name=result["tool_name"],
                    execution_time_ms=result["execution_time_ms"],
                    error=result["error"]
                )

                response.update(StateHelper.mark_step_complete(state, success=result["error"] is None))

                return response

        return APIAgentNode(api_agent)

    def _create_soap_agent_node(self) -> BaseNode:
        """Create node function for SOAP Agent."""
        soap_agent = self.agent_registry.get_agent(AgentType.SOAP_AGENT)

        if not soap_agent:
            logger.warning("⚠️ SOAP Agent not registered, using ToolExecutorNode")
            from .tool_executor_node import ToolExecutorNode
            return ToolExecutorNode(
                node_name="soap_agent",
                agent_type=AgentType.SOAP_AGENT,
                tool_registry=self.tool_registry,
                llm_provider=self.llm_provider,
                session_manager=self.session_manager
            )

        class SOAPAgentNode(BaseNode):
            def __init__(self, agent):
                super().__init__(node_name="soap_agent", agent_type=AgentType.SOAP_AGENT)
                self.agent = agent

            async def _execute(self, state: AgentState) -> dict:
                query = state["user_query"]
                current_step = StateHelper.get_current_step(state)
                parameters = current_step["parameters"] if current_step else {}

                result = await self.agent.execute(
                    query=query,
                    context=state.get("context"),
                    parameters=parameters
                )

                response = StateHelper.add_agent_result(
                    state,
                    agent_type=AgentType.SOAP_AGENT,
                    result_data=result["data"],
                    tool_name=result["tool_name"],
                    execution_time_ms=result["execution_time_ms"],
                    error=result["error"]
                )

                response.update(StateHelper.mark_step_complete(state, success=result["error"] is None))

                return response

        return SOAPAgentNode(soap_agent)

    def _create_consolidator_node(self) -> BaseNode:
        """Create consolidator node (Phase 4)."""
        return ConsolidatorNode(self.llm_provider)
