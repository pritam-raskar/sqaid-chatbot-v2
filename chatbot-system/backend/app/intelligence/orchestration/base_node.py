"""
Base node class for LangGraph Multi-Agent Orchestration.
All specialized nodes inherit from BaseNode for consistency.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import time

from app.intelligence.orchestration.types import AgentState, NodeResponse, AgentType
from app.intelligence.orchestration.state import StateHelper

logger = logging.getLogger(__name__)


class BaseNode(ABC):
    """
    Abstract base class for all nodes in the LangGraph workflow.

    Provides:
    - Standard logging
    - Error handling
    - Performance tracking
    - State manipulation helpers

    Usage:
        class MyCustomNode(BaseNode):
            def __init__(self):
                super().__init__(node_name="my_custom_node")

            def _execute(self, state: AgentState) -> NodeResponse:
                # Your logic here
                return {"some_key": "some_value"}
    """

    def __init__(self, node_name: str, agent_type: Optional[AgentType] = None):
        """
        Initialize base node.

        Args:
            node_name: Unique identifier for logging (e.g., "supervisor", "sql_agent")
            agent_type: Type of agent this node represents (optional)
        """
        self.node_name = node_name
        self.agent_type = agent_type
        logger.info(f"🔧 Initialized {self.node_name} node")

    async def __call__(self, state: AgentState) -> NodeResponse:
        """
        Entry point for node execution.
        Handles logging, timing, and error handling automatically.

        Args:
            state: Current AgentState from LangGraph

        Returns:
            NodeResponse (partial state update dict)

        This method:
        1. Logs entry
        2. Tracks execution time
        3. Calls _execute() (implemented by subclass)
        4. Handles errors
        5. Logs completion
        """
        logger.info(f"▶️ [{self.node_name}] Starting execution")
        start_time = time.time()

        try:
            # Call subclass implementation
            response = await self._execute(state)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Update performance metrics
            if "performance_metrics" not in response:
                response["performance_metrics"] = {}

            # Merge with existing metrics
            existing_metrics = state.get("performance_metrics", {})
            agents_called = existing_metrics.get("agents_called", [])
            agents_called.append({
                "node": self.node_name,
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat()
            })

            response["performance_metrics"] = {
                **existing_metrics,
                "agents_called": agents_called,
                f"{self.node_name}_time_ms": execution_time_ms
            }

            logger.info(
                f"✅ [{self.node_name}] Completed in {execution_time_ms:.2f}ms"
            )

            return response

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            error_msg = f"[{self.node_name}] Error: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)

            # Return error state update
            return StateHelper.add_error(state, error_msg)

    @abstractmethod
    async def _execute(self, state: AgentState) -> NodeResponse:
        """
        Main execution logic - MUST be implemented by subclass.

        Args:
            state: Current AgentState

        Returns:
            NodeResponse (partial state update dict)

        Example Implementation:
            async def _execute(self, state: AgentState) -> NodeResponse:
                query = state["user_query"]
                result = await self.do_something(query)

                return {
                    "sql_results": [result],
                    "current_step_index": state["current_step_index"] + 1
                }
        """
        pass

    def _log(self, message: str, level: str = "info"):
        """
        Convenience method for logging with node name prefix.

        Args:
            message: Log message
            level: Log level (debug, info, warning, error)
        """
        log_message = f"[{self.node_name}] {message}"

        if level == "debug":
            logger.debug(f"🔍 {log_message}")
        elif level == "info":
            logger.info(f"ℹ️ {log_message}")
        elif level == "warning":
            logger.warning(f"⚠️ {log_message}")
        elif level == "error":
            logger.error(f"❌ {log_message}")

    def _validate_state(self, state: AgentState, required_fields: list[str]) -> bool:
        """
        Validate that state contains required fields.

        Args:
            state: State to validate
            required_fields: List of field names that must be present

        Returns:
            True if valid, raises ValueError if not

        Example:
            self._validate_state(state, ["user_query", "execution_plan"])
        """
        missing_fields = [
            field for field in required_fields
            if field not in state or state[field] is None
        ]

        if missing_fields:
            error_msg = f"{self.node_name} requires fields: {missing_fields}"
            logger.error(f"❌ Validation failed: {error_msg}")
            raise ValueError(error_msg)

        logger.debug(f"✅ State validation passed for {self.node_name}")
        return True


class PassthroughNode(BaseNode):
    """
    Simple passthrough node for testing.
    Returns state unchanged with a log message.
    """

    def __init__(self, node_name: str = "passthrough"):
        super().__init__(node_name=node_name)

    async def _execute(self, state: AgentState) -> NodeResponse:
        """Simply log and pass through, incrementing step counter"""
        self._log(f"Passthrough node called with query: {state['user_query'][:50]}...")

        # Import here to avoid circular dependency
        from .state import StateHelper

        # Create a mock response for testing
        mock_response = {
            "message": "✅ LangGraph Multi-Agent Orchestration is working! (This is a test response from passthrough node)",
            "query": state["user_query"],
            "note": "Real agents are not yet registered. The SQL/API/SOAP agents will provide actual data when implemented."
        }

        # Mark step as complete and increment counter, plus add final response for testing
        result = StateHelper.mark_step_complete(state, success=True)
        result["final_response"] = f"Query: {state['user_query']}\n\nResponse: {mock_response['message']}\n\n{mock_response['note']}"

        return result
