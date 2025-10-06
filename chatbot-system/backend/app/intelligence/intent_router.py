"""
Intent Router using LangChain for intelligent query routing
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.language_models import BaseLLM
from langchain.memory import ConversationBufferMemory
from langchain_core.tools import BaseTool
import logging

from app.intelligence.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Result of intent routing"""
    intent: str
    confidence: float
    selected_tools: List[str]
    execution_plan: List[Dict[str, Any]]
    reasoning: str
    parameters: Dict[str, Any]


class IntentRouter:
    """
    Routes user queries to appropriate tools using LangChain ReAct agent
    Provides intelligent, dynamic routing without hardcoded logic
    """

    def __init__(
        self,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        memory: Optional[ConversationBufferMemory] = None
    ):
        """
        Initialize intent router

        Args:
            llm: LangChain LLM instance
            tool_registry: Tool registry for discovering tools
            memory: Optional conversation memory
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.memory = memory or ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        self.agent = None
        self.agent_executor = None

    async def initialize_agent(self) -> None:
        """Initialize LangChain ReAct agent with tools"""
        # Get all registered tools
        tools = self.tool_registry.get_all_tools()

        if not tools:
            logger.warning("No tools available for agent initialization")
            return

        # Create prompt template
        prompt = self._create_prompt_template()

        # Create ReAct agent
        self.agent = create_react_agent(
            llm=self.llm,
            tools=tools,
            prompt=prompt
        )

        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=tools,
            memory=self.memory,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

        logger.info(f"Initialized agent with {len(tools)} tools")

    def _create_prompt_template(self) -> PromptTemplate:
        """
        Create prompt template for ReAct agent

        Returns:
            PromptTemplate with system instructions and examples
        """
        template = """You are an intelligent assistant for a financial case management system.
Your job is to understand user queries and select the appropriate tools to answer them.

You have access to the following tools:
{tools}

When analyzing a query, consider:
1. What information is the user asking for?
2. Which data source(s) contain this information?
3. What filters or parameters are needed?
4. Should multiple tools be used together?

Use the following format:

Question: the input question you must answer
Thought: think about what information is needed and which tools to use
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Examples:

Question: What is the status of case #12345?
Thought: I need to query case information from the database
Action: query_case_details
Action Input: {{"case_id": "12345"}}
Observation: Case #12345 is in "Open" status, assigned to Agent Sarah
Thought: I now have the information needed
Final Answer: Case #12345 is currently in Open status and is assigned to Agent Sarah Johnson.

Question: Show me all high priority cases opened this week
Thought: I need to query cases with filters for priority and date
Action: query_cases_with_filters
Action Input: {{"priority": "high", "date_range": "this_week"}}
Observation: Found 5 high priority cases opened this week
Thought: I now have the results
Final Answer: There are 5 high priority cases opened this week: [list of cases]

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

        return PromptTemplate(
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
            template=template
        )

    async def route_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RoutingDecision:
        """
        Route a query to appropriate tools

        Args:
            query: User query
            context: Additional context (filters, user info, etc.)

        Returns:
            RoutingDecision with selected tools and execution plan
        """
        # Enrich query with context
        enriched_query = self._enrich_query(query, context)

        # Find best matching tools using semantic search
        best_tools = await self.tool_registry.find_best_tools(
            query=enriched_query,
            context=context,
            top_k=3
        )

        if not best_tools:
            logger.warning(f"No matching tools found for query: {query}")
            return RoutingDecision(
                intent="unknown",
                confidence=0.0,
                selected_tools=[],
                execution_plan=[],
                reasoning="No suitable tools found",
                parameters={}
            )

        # Classify intent
        intent = await self._classify_intent(query, context)

        # Create execution plan
        execution_plan = await self._create_execution_plan(
            query=query,
            intent=intent,
            tools=best_tools,
            context=context
        )

        # Calculate confidence
        confidence = self._calculate_confidence(best_tools, intent)

        return RoutingDecision(
            intent=intent,
            confidence=confidence,
            selected_tools=[tool.name for tool in best_tools],
            execution_plan=execution_plan,
            reasoning=f"Selected {len(best_tools)} tools for {intent} intent",
            parameters=self._extract_parameters(query, context)
        )

    def _enrich_query(self, query: str, context: Optional[Dict[str, Any]]) -> str:
        """Enrich query with contextual information"""
        if not context:
            return query

        enrichment_parts = [query]

        # Add current filters
        if "filters" in context:
            filters = context["filters"]
            if filters:
                filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
                enrichment_parts.append(f"Current filters: {filter_str}")

        # Add user role/permissions
        if "user_role" in context:
            enrichment_parts.append(f"User role: {context['user_role']}")

        # Add conversation history hints
        if "recent_topics" in context:
            topics = ", ".join(context["recent_topics"])
            enrichment_parts.append(f"Recent topics: {topics}")

        return ". ".join(enrichment_parts)

    async def _classify_intent(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Classify user intent from query

        Common intents:
        - query_data: Retrieve information
        - filter_data: Apply filters
        - aggregate_data: Get statistics/summaries
        - update_data: Modify data
        - visualize_data: Generate charts
        - export_data: Export results
        """
        query_lower = query.lower()

        # Simple keyword-based classification
        # In production, this would use LLM classification
        if any(word in query_lower for word in ["show", "get", "find", "list", "what", "which"]):
            return "query_data"
        elif any(word in query_lower for word in ["filter", "where", "with", "only"]):
            return "filter_data"
        elif any(word in query_lower for word in ["total", "count", "average", "sum", "how many"]):
            return "aggregate_data"
        elif any(word in query_lower for word in ["update", "change", "modify", "set"]):
            return "update_data"
        elif any(word in query_lower for word in ["chart", "graph", "visualize", "plot"]):
            return "visualize_data"
        elif any(word in query_lower for word in ["export", "download", "save"]):
            return "export_data"
        else:
            return "query_data"  # Default

    async def _create_execution_plan(
        self,
        query: str,
        intent: str,
        tools: List[BaseTool],
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create step-by-step execution plan

        Returns:
            List of execution steps with tool and parameters
        """
        plan = []

        # For now, create simple sequential plan
        # In production, this would use LLM to create sophisticated multi-step plans
        for i, tool in enumerate(tools):
            step = {
                "step": i + 1,
                "tool": tool.name,
                "action": intent,
                "parameters": self._extract_parameters(query, context),
                "description": f"Execute {tool.name} to {intent.replace('_', ' ')}"
            }
            plan.append(step)

        return plan

    def _extract_parameters(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract parameters from query and context

        This is a simple implementation. In production, use NER or LLM extraction
        """
        parameters = {}

        # Extract from context
        if context:
            if "filters" in context:
                parameters.update(context["filters"])
            if "page_context" in context:
                parameters["context"] = context["page_context"]

        # Extract case IDs
        import re
        case_ids = re.findall(r'#(\d+)', query)
        if case_ids:
            parameters["case_id"] = case_ids[0]

        # Extract priority
        query_lower = query.lower()
        if "high priority" in query_lower:
            parameters["priority"] = "high"
        elif "medium priority" in query_lower:
            parameters["priority"] = "medium"
        elif "low priority" in query_lower:
            parameters["priority"] = "low"

        # Extract status
        if "open" in query_lower:
            parameters["status"] = "open"
        elif "closed" in query_lower:
            parameters["status"] = "closed"
        elif "pending" in query_lower:
            parameters["status"] = "pending"

        # Extract date ranges
        if "today" in query_lower:
            parameters["date_range"] = "today"
        elif "this week" in query_lower:
            parameters["date_range"] = "this_week"
        elif "this month" in query_lower:
            parameters["date_range"] = "this_month"

        return parameters

    def _calculate_confidence(
        self,
        selected_tools: List[BaseTool],
        intent: str
    ) -> float:
        """Calculate confidence score for routing decision"""
        if not selected_tools:
            return 0.0

        # Base confidence from having tools
        confidence = 0.5

        # Boost for multiple matching tools
        if len(selected_tools) > 1:
            confidence += 0.2

        # Boost for clear intent
        if intent != "unknown":
            confidence += 0.3

        return min(confidence, 1.0)

    async def execute_routing(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the full routing and tool execution

        Args:
            query: User query
            context: Additional context

        Returns:
            Execution result with answer and intermediate steps
        """
        if not self.agent_executor:
            await self.initialize_agent()

        try:
            # Execute agent
            result = await self.agent_executor.ainvoke({
                "input": query,
                "chat_history": self.memory.chat_memory.messages
            })

            return {
                "answer": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", []),
                "success": True
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {
                "answer": f"I encountered an error: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "error": str(e)
            }

    def clear_memory(self) -> None:
        """Clear conversation memory"""
        self.memory.clear()
        logger.info("Cleared conversation memory")
