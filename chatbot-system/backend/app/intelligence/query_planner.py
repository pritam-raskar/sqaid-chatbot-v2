"""
Query Planner for multi-step query decomposition and planning
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of execution steps"""
    DATA_RETRIEVAL = "data_retrieval"
    FILTERING = "filtering"
    AGGREGATION = "aggregation"
    JOIN = "join"
    TRANSFORMATION = "transformation"
    VISUALIZATION = "visualization"


@dataclass
class ExecutionStep:
    """Single step in query execution plan"""
    step_id: int
    step_type: StepType
    tool_name: str
    parameters: Dict[str, Any]
    depends_on: List[int]  # Step IDs this step depends on
    description: str
    estimated_cost: float = 1.0  # Relative cost estimate


@dataclass
class QueryPlan:
    """Complete query execution plan"""
    query: str
    steps: List[ExecutionStep]
    total_steps: int
    estimated_total_cost: float
    can_parallelize: bool
    metadata: Dict[str, Any]


class QueryPlanner:
    """
    Plans multi-step query execution
    Decomposes complex queries into executable steps with dependency tracking
    """

    def __init__(self):
        """Initialize query planner"""
        self.step_counter = 0

    async def create_plan(
        self,
        query: str,
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> QueryPlan:
        """
        Create execution plan for a query

        Args:
            query: User query
            available_tools: List of available tool names
            context: Additional context

        Returns:
            QueryPlan with ordered execution steps
        """
        self.step_counter = 0
        steps = []

        # Analyze query complexity
        query_analysis = self._analyze_query(query)

        # Decompose into steps based on analysis
        if query_analysis["requires_join"]:
            steps.extend(self._plan_join_query(query, available_tools, context))
        elif query_analysis["requires_aggregation"]:
            steps.extend(self._plan_aggregation_query(query, available_tools, context))
        elif query_analysis["requires_filtering"]:
            steps.extend(self._plan_filter_query(query, available_tools, context))
        else:
            steps.extend(self._plan_simple_query(query, available_tools, context))

        # Check if steps can be parallelized
        can_parallelize = self._check_parallelization(steps)

        # Calculate total cost
        total_cost = sum(step.estimated_cost for step in steps)

        return QueryPlan(
            query=query,
            steps=steps,
            total_steps=len(steps),
            estimated_total_cost=total_cost,
            can_parallelize=can_parallelize,
            metadata={
                "analysis": query_analysis,
                "optimization_applied": True
            }
        )

    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to determine required operations

        Returns:
            Dictionary with query analysis results
        """
        query_lower = query.lower()

        return {
            "requires_join": self._requires_join(query_lower),
            "requires_aggregation": self._requires_aggregation(query_lower),
            "requires_filtering": self._requires_filtering(query_lower),
            "requires_sorting": any(word in query_lower for word in ["sort", "order by", "ranked"]),
            "requires_visualization": any(word in query_lower for word in ["chart", "graph", "plot", "visualize"]),
            "is_complex": len(query.split()) > 10 or "and" in query_lower or "or" in query_lower,
            "data_sources": self._identify_data_sources(query_lower)
        }

    def _requires_join(self, query_lower: str) -> bool:
        """Check if query requires joining multiple data sources"""
        join_indicators = [
            "and" in query_lower and "from" in query_lower,
            "combine" in query_lower,
            "merge" in query_lower,
            "with" in query_lower and "from" in query_lower
        ]
        return any(join_indicators)

    def _requires_aggregation(self, query_lower: str) -> bool:
        """Check if query requires aggregation"""
        agg_keywords = ["total", "count", "average", "sum", "max", "min", "how many", "statistics"]
        return any(keyword in query_lower for keyword in agg_keywords)

    def _requires_filtering(self, query_lower: str) -> bool:
        """Check if query requires filtering"""
        filter_keywords = ["where", "filter", "with", "only", "status", "priority", "date"]
        return any(keyword in query_lower for keyword in filter_keywords)

    def _identify_data_sources(self, query_lower: str) -> List[str]:
        """Identify mentioned data sources"""
        sources = []
        source_keywords = {
            "database": ["database", "db", "postgres", "oracle"],
            "api": ["api", "rest", "service"],
            "cases": ["case", "ticket", "request"],
            "users": ["user", "customer", "agent"],
            "transactions": ["transaction", "payment", "transfer"]
        }

        for source_type, keywords in source_keywords.items():
            if any(kw in query_lower for kw in keywords):
                sources.append(source_type)

        return sources

    def _plan_simple_query(
        self,
        query: str,
        available_tools: List[str],
        context: Optional[Dict[str, Any]]
    ) -> List[ExecutionStep]:
        """Plan for simple single-step query"""
        steps = []

        # Single data retrieval step
        step = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.DATA_RETRIEVAL,
            tool_name=self._select_tool(available_tools, "query"),
            parameters=self._extract_parameters(query, context),
            depends_on=[],
            description=f"Retrieve data for: {query}",
            estimated_cost=1.0
        )
        steps.append(step)

        return steps

    def _plan_filter_query(
        self,
        query: str,
        available_tools: List[str],
        context: Optional[Dict[str, Any]]
    ) -> List[ExecutionStep]:
        """Plan for query with filtering"""
        steps = []

        # Step 1: Retrieve data
        retrieval_step = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.DATA_RETRIEVAL,
            tool_name=self._select_tool(available_tools, "query"),
            parameters={},
            depends_on=[],
            description="Retrieve base dataset",
            estimated_cost=1.0
        )
        steps.append(retrieval_step)

        # Step 2: Apply filters
        filter_step = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.FILTERING,
            tool_name=self._select_tool(available_tools, "filter"),
            parameters=self._extract_parameters(query, context),
            depends_on=[retrieval_step.step_id],
            description="Apply filters to dataset",
            estimated_cost=0.5
        )
        steps.append(filter_step)

        return steps

    def _plan_aggregation_query(
        self,
        query: str,
        available_tools: List[str],
        context: Optional[Dict[str, Any]]
    ) -> List[ExecutionStep]:
        """Plan for query with aggregation"""
        steps = []

        # Step 1: Retrieve data
        retrieval_step = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.DATA_RETRIEVAL,
            tool_name=self._select_tool(available_tools, "query"),
            parameters=self._extract_parameters(query, context),
            depends_on=[],
            description="Retrieve data for aggregation",
            estimated_cost=1.0
        )
        steps.append(retrieval_step)

        # Step 2: Aggregate
        agg_step = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.AGGREGATION,
            tool_name=self._select_tool(available_tools, "aggregate"),
            parameters={"operation": self._detect_aggregation_type(query)},
            depends_on=[retrieval_step.step_id],
            description="Perform aggregation",
            estimated_cost=0.3
        )
        steps.append(agg_step)

        return steps

    def _plan_join_query(
        self,
        query: str,
        available_tools: List[str],
        context: Optional[Dict[str, Any]]
    ) -> List[ExecutionStep]:
        """Plan for query requiring joins across data sources"""
        steps = []

        # Identify data sources needed
        sources = self._identify_data_sources(query.lower())

        # Step 1: Retrieve from first source
        step1 = ExecutionStep(
            step_id=self._next_step_id(),
            step_type=StepType.DATA_RETRIEVAL,
            tool_name=self._select_tool(available_tools, "query", sources[0] if sources else None),
            parameters={"source": sources[0] if sources else "primary"},
            depends_on=[],
            description=f"Retrieve from {sources[0] if sources else 'primary source'}",
            estimated_cost=1.0
        )
        steps.append(step1)

        # Step 2: Retrieve from second source
        if len(sources) > 1:
            step2 = ExecutionStep(
                step_id=self._next_step_id(),
                step_type=StepType.DATA_RETRIEVAL,
                tool_name=self._select_tool(available_tools, "query", sources[1]),
                parameters={"source": sources[1]},
                depends_on=[],
                description=f"Retrieve from {sources[1]}",
                estimated_cost=1.0
            )
            steps.append(step2)

            # Step 3: Join results
            join_step = ExecutionStep(
                step_id=self._next_step_id(),
                step_type=StepType.JOIN,
                tool_name="join_data",
                parameters={"join_type": "inner"},
                depends_on=[step1.step_id, step2.step_id],
                description="Join data from multiple sources",
                estimated_cost=0.7
            )
            steps.append(join_step)

        return steps

    def _select_tool(
        self,
        available_tools: List[str],
        operation: str,
        preferred_source: Optional[str] = None
    ) -> str:
        """Select best tool for operation"""
        # Simple tool selection logic
        # In production, this would use semantic matching

        for tool in available_tools:
            tool_lower = tool.lower()
            if operation in tool_lower:
                if preferred_source and preferred_source in tool_lower:
                    return tool
                elif not preferred_source:
                    return tool

        # Fallback to first available tool
        return available_tools[0] if available_tools else "default_tool"

    def _extract_parameters(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract parameters from query"""
        params = {}

        if context and "filters" in context:
            params.update(context["filters"])

        # Extract case IDs
        import re
        case_ids = re.findall(r'#(\d+)', query)
        if case_ids:
            params["case_id"] = case_ids[0]

        return params

    def _detect_aggregation_type(self, query: str) -> str:
        """Detect type of aggregation needed"""
        query_lower = query.lower()

        if "count" in query_lower or "how many" in query_lower:
            return "count"
        elif "average" in query_lower or "avg" in query_lower:
            return "average"
        elif "total" in query_lower or "sum" in query_lower:
            return "sum"
        elif "max" in query_lower or "maximum" in query_lower:
            return "max"
        elif "min" in query_lower or "minimum" in query_lower:
            return "min"
        else:
            return "count"  # Default

    def _check_parallelization(self, steps: List[ExecutionStep]) -> bool:
        """Check if any steps can be executed in parallel"""
        # Steps can be parallelized if they have no dependencies on each other
        independent_steps = [step for step in steps if not step.depends_on]
        return len(independent_steps) > 1

    def _next_step_id(self) -> int:
        """Get next step ID"""
        self.step_counter += 1
        return self.step_counter

    def optimize_plan(self, plan: QueryPlan) -> QueryPlan:
        """
        Optimize execution plan

        Optimizations:
        1. Reorder steps for parallel execution
        2. Combine compatible steps
        3. Eliminate redundant steps
        """
        optimized_steps = plan.steps.copy()

        # Reorder for parallelization
        optimized_steps = self._reorder_for_parallelism(optimized_steps)

        # Recalculate metadata
        can_parallelize = self._check_parallelization(optimized_steps)
        total_cost = sum(step.estimated_cost for step in optimized_steps)

        return QueryPlan(
            query=plan.query,
            steps=optimized_steps,
            total_steps=len(optimized_steps),
            estimated_total_cost=total_cost,
            can_parallelize=can_parallelize,
            metadata={**plan.metadata, "optimized": True}
        )

    def _reorder_for_parallelism(self, steps: List[ExecutionStep]) -> List[ExecutionStep]:
        """Reorder steps to maximize parallelization opportunities"""
        # Simple implementation: independent steps first
        independent = [s for s in steps if not s.depends_on]
        dependent = [s for s in steps if s.depends_on]
        return independent + dependent

    async def execute_plan(
        self,
        plan: QueryPlan,
        tool_registry: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a query plan with dependency management and parallelization

        Args:
            plan: QueryPlan to execute
            tool_registry: ToolRegistry for accessing tools
            context: Execution context

        Returns:
            Dictionary with execution results and metadata
        """
        import asyncio
        from collections import defaultdict

        # Track step results
        step_results: Dict[int, Any] = {}
        step_errors: Dict[int, str] = {}

        # Build dependency graph
        dependency_graph = self._build_dependency_graph(plan.steps)

        # Topological sort to determine execution order
        execution_order = self._topological_sort(plan.steps, dependency_graph)

        if not execution_order:
            return {
                "success": False,
                "error": "Cyclic dependency detected in execution plan",
                "results": {}
            }

        logger.info(f"Executing plan with {len(plan.steps)} steps")

        # Execute steps in order, parallelizing where possible
        for level in execution_order:
            # Execute all steps in this level in parallel
            if len(level) > 1 and plan.can_parallelize:
                logger.info(f"Executing {len(level)} steps in parallel")
                results = await asyncio.gather(
                    *[self._execute_step(step, step_results, tool_registry, context)
                      for step in level],
                    return_exceptions=True
                )

                # Store results
                for step, result in zip(level, results):
                    if isinstance(result, Exception):
                        step_errors[step.step_id] = str(result)
                        logger.error(f"Step {step.step_id} failed: {result}")
                    else:
                        step_results[step.step_id] = result
            else:
                # Execute single step
                for step in level:
                    try:
                        result = await self._execute_step(
                            step, step_results, tool_registry, context
                        )
                        step_results[step.step_id] = result
                    except Exception as e:
                        step_errors[step.step_id] = str(e)
                        logger.error(f"Step {step.step_id} failed: {e}")

                        # Check if we should stop on error
                        if not context or not context.get("continue_on_error", False):
                            return {
                                "success": False,
                                "error": f"Step {step.step_id} failed: {e}",
                                "partial_results": step_results,
                                "errors": step_errors
                            }

        # Aggregate final results
        final_result = self._aggregate_results(step_results, plan)

        return {
            "success": len(step_errors) == 0,
            "result": final_result,
            "step_results": step_results,
            "errors": step_errors if step_errors else None,
            "steps_executed": len(step_results),
            "total_steps": len(plan.steps)
        }

    def _build_dependency_graph(
        self,
        steps: List[ExecutionStep]
    ) -> Dict[int, List[int]]:
        """Build dependency graph from execution steps"""
        graph = defaultdict(list)

        for step in steps:
            if step.depends_on:
                for dep_id in step.depends_on:
                    graph[dep_id].append(step.step_id)
            else:
                # No dependencies
                graph[step.step_id] = []

        return dict(graph)

    def _topological_sort(
        self,
        steps: List[ExecutionStep],
        dependency_graph: Dict[int, List[int]]
    ) -> List[List[ExecutionStep]]:
        """
        Topological sort with level grouping for parallelization

        Returns:
            List of levels, where each level contains steps that can run in parallel
        """
        from collections import deque

        # Calculate in-degree for each step
        in_degree = {step.step_id: len(step.depends_on) for step in steps}
        step_map = {step.step_id: step for step in steps}

        # Find all steps with no dependencies
        queue = deque([step_id for step_id, degree in in_degree.items() if degree == 0])

        levels = []
        visited = set()

        while queue:
            # All steps in queue can execute in parallel (same level)
            level = []
            level_size = len(queue)

            for _ in range(level_size):
                step_id = queue.popleft()
                visited.add(step_id)
                level.append(step_map[step_id])

                # Reduce in-degree for dependent steps
                for dependent_id in dependency_graph.get(step_id, []):
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

            levels.append(level)

        # Check for cycles
        if len(visited) != len(steps):
            logger.error("Cyclic dependency detected in execution plan")
            return []

        return levels

    async def _execute_step(
        self,
        step: ExecutionStep,
        step_results: Dict[int, Any],
        tool_registry: Any,
        context: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Execute a single execution step

        Args:
            step: ExecutionStep to execute
            step_results: Results from previous steps
            tool_registry: ToolRegistry for tool access
            context: Execution context

        Returns:
            Step execution result
        """
        logger.info(f"Executing step {step.step_id}: {step.description}")

        # Get tool from registry
        tool = tool_registry.get_tool(step.tool_name)

        if not tool:
            raise Exception(f"Tool '{step.tool_name}' not found in registry")

        # Prepare parameters (may include results from dependencies)
        parameters = step.parameters.copy()

        # Add results from dependent steps if needed
        for dep_id in step.depends_on:
            if dep_id in step_results:
                parameters[f"step_{dep_id}_result"] = step_results[dep_id]

        # Execute tool
        try:
            result = await tool._arun(**parameters)
            logger.info(f"Step {step.step_id} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Step {step.step_id} execution failed: {e}")
            raise

    def _aggregate_results(
        self,
        step_results: Dict[int, Any],
        plan: QueryPlan
    ) -> Any:
        """
        Aggregate results from all steps into final result

        Args:
            step_results: Results from all executed steps
            plan: Original query plan

        Returns:
            Aggregated final result
        """
        # If there's only one step, return its result
        if len(step_results) == 1:
            return list(step_results.values())[0]

        # Find steps with no dependents (final steps)
        final_steps = []
        all_dependencies = set()

        for step in plan.steps:
            all_dependencies.update(step.depends_on)

        for step in plan.steps:
            if step.step_id not in all_dependencies:
                final_steps.append(step.step_id)

        # Aggregate final step results
        if len(final_steps) == 1:
            return step_results.get(final_steps[0])
        else:
            # Multiple final steps - return all
            return {
                f"step_{step_id}": step_results.get(step_id)
                for step_id in final_steps
                if step_id in step_results
            }
