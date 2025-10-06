"""
Routing Logic - Determines which agent to execute next based on state.
"""
import logging
from typing import Literal

from app.intelligence.orchestration.types import AgentState, AgentType, RoutingDecision

logger = logging.getLogger(__name__)


def route_from_supervisor(state: AgentState) -> RoutingDecision:
    """
    Route from supervisor node to appropriate agent or end.

    Args:
        state: Current AgentState

    Returns:
        RoutingDecision string indicating next node

    Logic:
        - Check next_agent field in state
        - Route to that agent or END
    """
    next_agent = state.get("next_agent")

    if not next_agent:
        logger.info("🏁 No next agent, routing to END")
        return "end"

    # Map AgentType to routing decision
    routing_map = {
        AgentType.SQL_AGENT: "sql_agent",
        AgentType.API_AGENT: "api_agent",
        AgentType.SOAP_AGENT: "soap_agent",
        AgentType.CONSOLIDATOR: "consolidator"
    }

    decision = routing_map.get(next_agent, "end")

    logger.info(f"🔀 Routing from supervisor to: {decision}")

    return decision


def route_from_agent(state: AgentState) -> Literal["supervisor", "end"]:
    """
    Route from agent back to supervisor or end.

    Args:
        state: Current AgentState

    Returns:
        "supervisor" to continue with next step, or "end" if done

    Logic:
        - If more steps remain, route back to supervisor
        - If plan complete, route to END
    """
    should_continue = state.get("should_continue", False)

    # Check if plan is complete
    plan = state.get("execution_plan")
    if plan:
        current_idx = state.get("current_step_index", 0)
        plan_complete = current_idx >= len(plan["steps"])

        if plan_complete:
            logger.info("🏁 Plan complete, routing to END")
            return "end"

    if should_continue:
        logger.info("🔄 Routing back to supervisor for next step")
        return "supervisor"
    else:
        logger.info("🏁 Should not continue, routing to END")
        return "end"


def should_continue_workflow(state: AgentState) -> bool:
    """
    Determine if workflow should continue.

    Args:
        state: Current AgentState

    Returns:
        True if should continue, False otherwise
    """
    # Check for errors
    if state.get("errors") and len(state["errors"]) > 0:
        logger.warning(f"⚠️ Errors detected: {len(state['errors'])}")
        # Continue anyway to try to complete what we can
        # return False

    # Check should_continue flag
    should_continue = state.get("should_continue", True)

    # Check if we have a next agent
    has_next_agent = state.get("next_agent") is not None

    result = should_continue and has_next_agent

    logger.debug(f"Should continue workflow: {result}")

    return result
