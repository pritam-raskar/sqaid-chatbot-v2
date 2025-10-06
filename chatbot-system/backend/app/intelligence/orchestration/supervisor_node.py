"""
Supervisor Node - Analyzes queries and creates execution plans.
Entry point for all LangGraph workflows.
"""
import logging
from typing import Dict, Any

from app.intelligence.orchestration.base_node import BaseNode
from app.intelligence.orchestration.types import AgentState, NodeResponse, AgentType
from app.intelligence.orchestration.execution_planner import ExecutionPlanner
from app.intelligence.orchestration.state import StateHelper

logger = logging.getLogger(__name__)


class SupervisorNode(BaseNode):
    """
    Supervisor node that analyzes queries and creates execution plans.

    Responsibilities:
    - Analyze user query
    - Create multi-step execution plan
    - Determine which agent(s) to call
    - Set routing decisions

    This is always the first node in the workflow.
    """

    def __init__(self, execution_planner: ExecutionPlanner):
        """
        Initialize supervisor node.

        Args:
            execution_planner: ExecutionPlanner instance for creating plans
        """
        super().__init__(node_name="supervisor", agent_type=AgentType.SUPERVISOR)
        self.execution_planner = execution_planner

        logger.info("✅ SupervisorNode initialized")

    async def _execute(self, state: AgentState) -> NodeResponse:
        """
        Execute supervisor logic.

        Args:
            state: Current AgentState

        Returns:
            NodeResponse with execution_plan and next_agent
        """
        query = state["user_query"]

        self._log(f"Analyzing query: {query[:100]}...")

        # Check if we already have a plan
        if state.get("execution_plan"):
            self._log("Using existing execution plan", "debug")
            plan = state["execution_plan"]
        else:
            # Create new execution plan
            self._log("Creating new execution plan...")
            context = state.get("context", {})

            plan = await self.execution_planner.create_plan(query, context)

        # Get current step
        current_idx = state.get("current_step_index", 0)

        # Check if plan is complete
        # Use plan from local variable, not state (in case we just created it)
        if current_idx >= len(plan["steps"]):
            self._log("Execution plan complete, routing to consolidator or end")

            # If we have results from multiple agents, go to consolidator
            all_results = StateHelper.get_all_results(state)
            if len(all_results) > 1 or plan.get("requires_consolidation"):
                next_agent = AgentType.CONSOLIDATOR
            else:
                next_agent = None  # Will route to END

            return {
                "next_agent": next_agent,
                "should_continue": next_agent is not None
            }

        # Get current step to execute
        current_step = plan["steps"][current_idx]

        self._log(
            f"Routing to {current_step['agent_type'].value} "
            f"(step {current_idx + 1}/{len(plan['steps'])})"
        )

        return {
            "execution_plan": plan,
            "next_agent": current_step["agent_type"],
            "should_continue": True
        }
