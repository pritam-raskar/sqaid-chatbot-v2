"""
State management utilities for LangGraph Multi-Agent Orchestration.
Provides factory functions and state manipulation helpers.
"""
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging

from app.intelligence.orchestration.types import (
    AgentState,
    ExecutionPlan,
    ExecutionStep,
    AgentType,
    ExecutionStepStatus,
    AgentResult
)

logger = logging.getLogger(__name__)


class StateFactory:
    """
    Factory class for creating initial state objects.
    Centralizes state creation logic and ensures consistency.
    """

    @staticmethod
    def create_initial_state(
        user_query: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentState:
        """
        Create an initial AgentState for a new query.

        Args:
            user_query: The user's question
            session_id: Unique session identifier
            context: Optional additional context (user prefs, filters, etc.)

        Returns:
            Fully initialized AgentState ready for LangGraph execution

        Example:
            state = StateFactory.create_initial_state(
                user_query="How many alerts do we have?",
                session_id="abc-123"
            )
        """
        logger.info(f"📝 Creating initial state for query: {user_query[:50]}...")

        initial_state: AgentState = {
            # Input
            "user_query": user_query,
            "session_id": session_id,

            # Planning
            "execution_plan": None,  # Will be set by supervisor
            "current_step_index": 0,

            # Execution Results (start empty, will accumulate)
            "sql_results": [],
            "api_results": [],
            "soap_results": [],

            # Processing
            "intermediate_data": {},
            "context": context or {},

            # Output
            "final_response": "",
            "consolidated_data": None,

            # Metadata
            "messages": [{
                "role": "user",
                "content": user_query,
                "timestamp": datetime.utcnow().isoformat()
            }],
            "errors": [],
            "performance_metrics": {
                "start_time": datetime.utcnow().isoformat(),
                "total_steps": 0,
                "agents_called": []
            },

            # Control Flow
            "next_agent": AgentType.SUPERVISOR,  # Always start with supervisor
            "should_continue": True
        }

        logger.debug(f"✅ Initial state created for session {session_id}")
        return initial_state

    @staticmethod
    def create_execution_plan(
        query: str,
        steps: list[ExecutionStep],
        requires_consolidation: bool = False,
        estimated_complexity: int = 5
    ) -> ExecutionPlan:
        """
        Create an ExecutionPlan for multi-step query execution.

        Args:
            query: Original user query
            steps: List of execution steps in dependency order
            requires_consolidation: Whether cross-source merging is needed
            estimated_complexity: Complexity score 1-10 (1=simple, 10=very complex)

        Returns:
            ExecutionPlan ready to be executed

        Example:
            plan = StateFactory.create_execution_plan(
                query="Show me alerts for Engineering users",
                steps=[
                    {
                        "step_id": "step_1",
                        "agent_type": AgentType.API_AGENT,
                        "description": "Get Engineering department users",
                        ...
                    },
                    {
                        "step_id": "step_2",
                        "agent_type": AgentType.SQL_AGENT,
                        "description": "Get alerts for those users",
                        "depends_on": ["step_1"],
                        ...
                    }
                ],
                requires_consolidation=True,
                estimated_complexity=7
            )
        """
        plan_id = str(uuid.uuid4())

        plan: ExecutionPlan = {
            "plan_id": plan_id,
            "query": query,
            "steps": steps,
            "requires_consolidation": requires_consolidation,
            "estimated_complexity": estimated_complexity,
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(
            f"🗺️ Created execution plan {plan_id[:8]}... with {len(steps)} steps, "
            f"complexity={estimated_complexity}, consolidation={requires_consolidation}"
        )

        return plan

    @staticmethod
    def create_execution_step(
        step_id: str,
        agent_type: AgentType,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        depends_on: Optional[list[str]] = None
    ) -> ExecutionStep:
        """
        Create a single ExecutionStep.

        Args:
            step_id: Unique identifier (e.g., "step_1", "step_2")
            agent_type: Which agent will execute this step
            description: What this step does
            parameters: Parameters for the agent/tool
            tool_name: Specific tool to use (optional, agent can choose)
            depends_on: List of step_ids that must complete first

        Returns:
            ExecutionStep ready to be added to a plan

        Example:
            step = StateFactory.create_execution_step(
                step_id="step_1",
                agent_type=AgentType.SQL_AGENT,
                description="Count total alerts",
                parameters={"query": "Count all alerts"}
            )
        """
        step: ExecutionStep = {
            "step_id": step_id,
            "agent_type": agent_type,
            "description": description,
            "tool_name": tool_name,
            "parameters": parameters or {},
            "depends_on": depends_on or [],
            "status": ExecutionStepStatus.PENDING,
            "result": None,
            "error": None
        }

        logger.debug(f"📋 Created execution step {step_id}: {description}")
        return step


class StateHelper:
    """
    Helper methods for manipulating and querying state.
    Provides common operations on AgentState.
    """

    @staticmethod
    def add_agent_result(
        state: AgentState,
        agent_type: AgentType,
        result_data: Any,
        tool_name: Optional[str] = None,
        execution_time_ms: float = 0,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a result to the appropriate results list in state.

        Args:
            state: Current state
            agent_type: Which agent produced the result
            result_data: The actual data
            tool_name: Tool that was used
            execution_time_ms: How long it took
            error: Error message if failed

        Returns:
            Partial state update dict to return from node

        Example:
            # In an agent node:
            return StateHelper.add_agent_result(
                state=state,
                agent_type=AgentType.SQL_AGENT,
                result_data={"count": 29},
                tool_name="query_postgresql_cm_alerts",
                execution_time_ms=125.5
            )
        """
        result: AgentResult = {
            "agent_type": agent_type,
            "tool_name": tool_name,
            "data": result_data,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "step_index": state["current_step_index"]
            },
            "error": error,
            "execution_time_ms": execution_time_ms
        }

        logger.info(
            f"✨ Adding result from {agent_type.value}: "
            f"{tool_name or 'unknown_tool'} ({execution_time_ms:.1f}ms)"
        )

        # Determine which result list to append to
        if agent_type == AgentType.SQL_AGENT:
            return {"sql_results": [result]}
        elif agent_type == AgentType.API_AGENT:
            return {"api_results": [result]}
        elif agent_type == AgentType.SOAP_AGENT:
            return {"soap_results": [result]}
        else:
            logger.warning(f"⚠️ Unknown agent type: {agent_type}")
            return {}

    @staticmethod
    def mark_step_complete(
        state: AgentState,
        success: bool = True,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark current step as complete and advance to next step.

        Args:
            state: Current state
            success: Whether step succeeded
            error: Error message if failed

        Returns:
            Partial state update dict

        Example:
            return StateHelper.mark_step_complete(state, success=True)
        """
        plan = state.get("execution_plan")
        if not plan:
            return {"current_step_index": state["current_step_index"] + 1}

        current_idx = state["current_step_index"]

        # Update step status
        if current_idx < len(plan["steps"]):
            step = plan["steps"][current_idx]
            step["status"] = ExecutionStepStatus.COMPLETED if success else ExecutionStepStatus.FAILED
            step["error"] = error

            status_emoji = "✅" if success else "❌"
            logger.info(
                f"{status_emoji} Step {current_idx + 1}/{len(plan['steps'])} complete: "
                f"{step['description']}"
            )

        # Advance to next step
        next_idx = current_idx + 1

        return {
            "execution_plan": plan,
            "current_step_index": next_idx
        }

    @staticmethod
    def add_error(state: AgentState, error_message: str) -> Dict[str, Any]:
        """
        Add an error to the state error list.

        Args:
            state: Current state
            error_message: Error description

        Returns:
            Partial state update dict
        """
        logger.error(f"❌ Adding error to state: {error_message}")
        return {
            "errors": [f"[{datetime.utcnow().isoformat()}] {error_message}"]
        }

    @staticmethod
    def get_all_results(state: AgentState) -> list[AgentResult]:
        """
        Get all results from all agents combined.

        Args:
            state: Current state

        Returns:
            List of all AgentResults across all agent types
        """
        all_results = (
            state.get("sql_results", []) +
            state.get("api_results", []) +
            state.get("soap_results", [])
        )

        logger.debug(f"📊 Retrieved {len(all_results)} total results from state")
        return all_results

    @staticmethod
    def has_errors(state: AgentState) -> bool:
        """Check if state contains any errors"""
        has_err = len(state.get("errors", [])) > 0
        if has_err:
            logger.warning(f"⚠️ State contains {len(state.get('errors', []))} errors")
        return has_err

    @staticmethod
    def get_current_step(state: AgentState) -> Optional[ExecutionStep]:
        """Get the current execution step being processed"""
        plan = state.get("execution_plan")
        if not plan:
            return None

        idx = state.get("current_step_index", 0)
        if idx < len(plan["steps"]):
            step = plan["steps"][idx]
            logger.debug(
                f"🎯 Current step {idx + 1}/{len(plan['steps'])}: {step['description']}"
            )
            return step

        return None

    @staticmethod
    def is_plan_complete(state: AgentState) -> bool:
        """Check if all steps in the execution plan are complete"""
        plan = state.get("execution_plan")
        if not plan:
            return True  # No plan means nothing to execute

        current_idx = state.get("current_step_index", 0)
        is_complete = current_idx >= len(plan["steps"])

        if is_complete:
            logger.info(f"🎉 Execution plan complete: {len(plan['steps'])} steps finished")

        return is_complete
