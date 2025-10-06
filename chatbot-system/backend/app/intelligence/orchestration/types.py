"""
Type definitions for LangGraph Multi-Agent Orchestration.
Provides type safety and clear interfaces between components.
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal, Annotated
from enum import Enum
import operator


class DataSourceType(str, Enum):
    """Enumeration of available data sources"""
    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    REST_API = "rest_api"
    SOAP_API = "soap_api"


class AgentType(str, Enum):
    """Types of specialized agents in the system"""
    SUPERVISOR = "supervisor"
    SQL_AGENT = "sql_agent"
    API_AGENT = "api_agent"
    SOAP_AGENT = "soap_agent"
    CONSOLIDATOR = "consolidator"


class ExecutionStepStatus(str, Enum):
    """Status of individual execution steps"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Type aliases for clarity
QueryString = str
AgentName = str
ToolName = str
ResultData = Dict[str, Any]


class ExecutionStep(TypedDict):
    """
    Represents a single step in multi-step query execution.

    Fields:
        step_id: Unique identifier for this step
        agent_type: Which agent should handle this step
        description: Human-readable description of what this step does
        tool_name: Optional specific tool to use
        parameters: Parameters to pass to the agent/tool
        depends_on: List of step_ids that must complete before this step
        status: Current execution status
        result: Result data after execution (None if not yet executed)
        error: Error message if step failed (None if successful)
    """
    step_id: str
    agent_type: AgentType
    description: str
    tool_name: Optional[ToolName]
    parameters: Dict[str, Any]
    depends_on: List[str]  # step_ids
    status: ExecutionStepStatus
    result: Optional[ResultData]
    error: Optional[str]


class ExecutionPlan(TypedDict):
    """
    Complete execution plan for a user query.

    Fields:
        plan_id: Unique identifier for this plan
        query: Original user query
        steps: List of execution steps in dependency order
        requires_consolidation: Whether results need cross-source merging
        estimated_complexity: Complexity score (1-10)
        created_at: Timestamp when plan was created
    """
    plan_id: str
    query: QueryString
    steps: List[ExecutionStep]
    requires_consolidation: bool
    estimated_complexity: int
    created_at: str


class AgentResult(TypedDict):
    """
    Result returned by an individual agent.

    Fields:
        agent_type: Which agent produced this result
        tool_name: Specific tool that was used
        data: The actual result data
        metadata: Additional information (row count, query time, etc.)
        error: Error message if agent failed
        execution_time_ms: How long the agent took
    """
    agent_type: AgentType
    tool_name: Optional[ToolName]
    data: Any
    metadata: Dict[str, Any]
    error: Optional[str]
    execution_time_ms: float


# Helper function to create accumulating list type
# Using operator.add allows LangGraph to append items
def AccumulatingList(item_type):
    """Create an Annotated list type that accumulates items instead of replacing"""
    return Annotated[List[item_type], operator.add]


class AgentState(TypedDict):
    """
    Shared state that flows through all agents in the LangGraph workflow.
    This is the central data structure that gets updated by each node.

    State Flow:
        User Input → Supervisor → Specialized Agents → Consolidator → Response

    Fields:
        # Input
        user_query: Original question from user
        session_id: User session identifier

        # Planning
        execution_plan: Multi-step plan created by supervisor
        current_step_index: Which step is currently executing

        # Execution Results (Accumulating)
        sql_results: Results from SQL agent (accumulates multiple calls)
        api_results: Results from API agent (accumulates multiple calls)
        soap_results: Results from SOAP agent (accumulates multiple calls)

        # Processing
        intermediate_data: Temporary data storage between steps
        context: Additional context for agents (user preferences, filters, etc.)

        # Output
        final_response: Formatted response for user
        consolidated_data: Merged data from multiple sources

        # Metadata
        messages: Chat history for context
        errors: List of errors encountered (accumulates)
        performance_metrics: Timing and resource usage data

        # Control Flow
        next_agent: Which agent to route to next (dynamic routing)
        should_continue: Whether to continue execution or stop
    """
    # Input
    user_query: QueryString
    session_id: str

    # Planning
    execution_plan: Optional[ExecutionPlan]
    current_step_index: int

    # Execution Results (these accumulate using operator.add)
    sql_results: Annotated[List[AgentResult], operator.add]
    api_results: Annotated[List[AgentResult], operator.add]
    soap_results: Annotated[List[AgentResult], operator.add]

    # Processing
    intermediate_data: Dict[str, Any]
    context: Dict[str, Any]

    # Output
    final_response: str
    consolidated_data: Optional[ResultData]

    # Metadata
    messages: Annotated[List[Dict[str, str]], operator.add]
    errors: Annotated[List[str], operator.add]
    performance_metrics: Dict[str, Any]

    # Control Flow
    next_agent: Optional[AgentType]
    should_continue: bool


class NodeResponse(TypedDict):
    """
    Standard response format returned by all nodes.
    Nodes update the state by returning a partial AgentState dict.

    Example:
        def my_node(state: AgentState) -> NodeResponse:
            # Do work...
            return {
                "sql_results": [result],
                "current_step_index": state["current_step_index"] + 1
            }
    """
    pass  # This is intentionally a flexible dict for partial state updates


# Helper type for routing functions
RoutingDecision = Literal["sql_agent", "api_agent", "soap_agent", "consolidator", "end"]


class ToolMetadataDict(TypedDict):
    """Metadata about available tools for planning"""
    tool_name: str
    data_source: DataSourceType
    description: str
    capabilities: List[str]
    keywords: List[str]
