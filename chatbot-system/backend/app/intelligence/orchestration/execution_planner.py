"""
Execution Planner - Analyzes queries and generates multi-step execution plans.
Uses LLM to understand query requirements and plan optimal execution strategy.
"""
from typing import List, Dict, Any, Optional
import logging
import re
import json
from datetime import datetime

from app.intelligence.orchestration.types import (
    ExecutionPlan,
    ExecutionStep,
    AgentType,
    ExecutionStepStatus,
    ToolMetadataDict
)
from app.intelligence.orchestration.state import StateFactory
from app.llm.base_provider import BaseLLMProvider
from app.intelligence.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ExecutionPlanner:
    """
    Creates execution plans from natural language queries.

    Responsibilities:
    - Analyze query intent and requirements
    - Identify which data sources are needed
    - Generate step-by-step execution plan
    - Determine dependencies between steps
    - Estimate query complexity

    Example:
        Query: "Show me alerts for users in Engineering department"

        Plan:
            Step 1: APIAgent - Get Engineering users
            Step 2: SQLAgent - Get alerts for those users (depends on Step 1)
            Consolidation: Yes (merge user data with alert data)
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry
    ):
        """
        Initialize execution planner.

        Args:
            llm_provider: LLM for query analysis
            tool_registry: Registry with available tools for planning
        """
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.available_tools = self._get_tool_metadata()

        logger.info(
            f"🔧 ExecutionPlanner initialized with {len(self.available_tools)} tools"
        )

    def _extract_response_text(self, response: Dict[str, Any]) -> str:
        """
        Extract text content from LLM response.
        Handles different provider response formats (Anthropic, OpenAI, Eliza, etc.).

        Args:
            response: Raw LLM response

        Returns:
            Extracted text content
        """
        # Try Anthropic format
        if "content" in response and isinstance(response["content"], list):
            if len(response["content"]) > 0 and "text" in response["content"][0]:
                return response["content"][0]["text"]

        # Try OpenAI format
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
            if "text" in choice:
                return choice["text"]

        # Try simple content format (Eliza and others)
        if "content" in response and isinstance(response["content"], str):
            return response["content"]

        # Try message.content format
        if "message" in response and "content" in response["message"]:
            return response["message"]["content"]

        # Try direct text field
        if "text" in response:
            return response["text"]

        # Fallback - return as JSON string
        logger.warning(f"⚠️ Unknown response format, returning as JSON")
        return json.dumps(response, indent=2)

    def _get_tool_metadata(self) -> List[ToolMetadataDict]:
        """
        Get metadata about available tools for planning.

        Returns:
            List of tool metadata dicts
        """
        metadata = []

        for tool_name, tool in self.tool_registry.tools.items():
            tool_meta = self.tool_registry.metadata.get(tool_name)
            if tool_meta:
                metadata.append({
                    "tool_name": tool_name,
                    "data_source": tool_meta.data_source,
                    "description": tool.description,
                    "capabilities": tool_meta.capabilities,
                    "keywords": tool_meta.keywords
                })

        logger.debug(f"📊 Collected metadata for {len(metadata)} tools")
        return metadata

    async def create_plan(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Create execution plan for a query.

        Args:
            query: Natural language query
            context: Additional context (user preferences, previous results, etc.)

        Returns:
            ExecutionPlan with steps and dependencies
        """
        logger.info(f"📋 Creating execution plan for: {query[:100]}...")

        # Analyze query to understand requirements
        analysis = await self._analyze_query(query, context)

        # Generate execution steps
        steps = await self._generate_steps(query, analysis)

        # Create execution plan
        plan = StateFactory.create_execution_plan(
            query=query,
            steps=steps,
            requires_consolidation=analysis["requires_consolidation"],
            estimated_complexity=analysis["complexity"]
        )

        logger.info(
            f"✅ Created plan {plan['plan_id'][:8]}... with {len(steps)} steps, "
            f"complexity={plan['estimated_complexity']}, "
            f"consolidation={plan['requires_consolidation']}"
        )

        return plan

    async def _analyze_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze query to understand what data sources are needed.

        Returns:
            Analysis dict with required_sources, requires_consolidation, complexity
        """
        logger.info(f"🔍 Analyzing query requirements...")

        # Build analysis prompt
        prompt = self._build_analysis_prompt(query, context)

        # Log the prompt
        logger.info("=" * 80)
        logger.info("📋 [EXECUTION PLANNER] Prompt:")
        logger.info("-" * 80)
        logger.info(prompt)
        logger.info("=" * 80)

        # Get model from settings (if available)
        model = None
        try:
            from app.core.config import get_settings
            settings = get_settings()
            model = settings.get_model_for_agent("execution_planner")
            logger.info(f"🤖 [EXECUTION PLANNER] Using model: {model}")
        except Exception as e:
            logger.debug(f"Could not get model from settings: {e}")
            # Fallback to provider's default model
            if hasattr(self.llm_provider, 'model'):
                model = self.llm_provider.model

        # Call LLM
        try:
            # Prepare kwargs for model parameter
            llm_kwargs = {"temperature": 0}  # Deterministic for planning
            if model:
                llm_kwargs["model"] = model

            response = await self.llm_provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                **llm_kwargs
            )

            # Extract content from response (works with all providers)
            content = self._extract_response_text(response)

            # Log the response
            logger.info("=" * 80)
            logger.info("📋 [EXECUTION PLANNER] Response:")
            logger.info("-" * 80)
            logger.info(content)
            logger.info("=" * 80)

            logger.debug(f"📝 LLM response: {content[:200]}...")

            # Parse LLM response
            analysis = self._parse_analysis_response(content)

            logger.info(
                f"✅ Analysis complete: sources={analysis['required_sources']}, "
                f"complexity={analysis['complexity']}"
            )

            return analysis

        except Exception as e:
            logger.error(f"❌ Query analysis failed: {e}", exc_info=True)
            logger.warning(f"🔄 Falling back to heuristic analysis...")

            # Fallback to simple heuristics
            return self._fallback_analysis(query)

    def _build_analysis_prompt(
        self,
        query: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for LLM query analysis."""
        # Format available data sources
        sources_by_type = {}
        for tool_meta in self.available_tools:
            source_type = tool_meta["data_source"]
            if source_type not in sources_by_type:
                sources_by_type[source_type] = []
            sources_by_type[source_type].append({
                "name": tool_meta["tool_name"],
                "description": tool_meta["description"],
                "keywords": tool_meta["keywords"]
            })

        sources_text = ""
        for source_type, tools in sources_by_type.items():
            sources_text += f"\n{source_type}:\n"
            for tool in tools[:3]:  # Show first 3 tools per source
                sources_text += f"  - {tool['name']}: {tool['description'][:80]}...\n"

        prompt = f"""Analyze this user query and determine the execution requirements.

Query: "{query}"

Available Data Sources:
{sources_text}

Analyze and respond in this exact format:

REQUIRED_SOURCES: [comma-separated list of data source types needed, e.g., postgresql, rest_api, soap_api]
REQUIRES_CONSOLIDATION: [yes/no - whether data from multiple sources needs to be merged]
COMPLEXITY: [number 1-10, where 1=simple single-table query, 10=complex multi-source with joins]
QUERY_TYPE: [one of: count, list, aggregate, filter, join, multi_step]
REASONING: [brief explanation]

Example Response:
REQUIRED_SOURCES: rest_api, postgresql
REQUIRES_CONSOLIDATION: yes
COMPLEXITY: 7
QUERY_TYPE: multi_step
REASONING: Need to get users from REST API, then query alerts for those users from database.
"""

        return prompt

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM analysis response."""
        analysis = {
            "required_sources": [],
            "requires_consolidation": False,
            "complexity": 5,
            "query_type": "unknown",
            "reasoning": ""
        }

        # Extract REQUIRED_SOURCES
        sources_match = re.search(r'REQUIRED_SOURCES:\s*\[?([^\]\n]+)\]?', response, re.IGNORECASE)
        if sources_match:
            sources_str = sources_match.group(1).strip()
            # Handle both "postgresql_db" and "postgresql_db, rest_api" formats
            analysis["required_sources"] = [
                s.strip() for s in sources_str.split(',') if s.strip()
            ]

        # Extract REQUIRES_CONSOLIDATION
        consolidation_match = re.search(r'REQUIRES_CONSOLIDATION:\s*(yes|no)', response, re.IGNORECASE)
        if consolidation_match:
            analysis["requires_consolidation"] = consolidation_match.group(1).lower() == "yes"

        # Extract COMPLEXITY
        complexity_match = re.search(r'COMPLEXITY:\s*(\d+)', response, re.IGNORECASE)
        if complexity_match:
            analysis["complexity"] = int(complexity_match.group(1))

        # Extract QUERY_TYPE
        type_match = re.search(r'QUERY_TYPE:\s*(\w+)', response, re.IGNORECASE)
        if type_match:
            analysis["query_type"] = type_match.group(1)

        # Extract REASONING
        reasoning_match = re.search(r'REASONING:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            analysis["reasoning"] = reasoning_match.group(1).strip()

        logger.debug(f"📊 Parsed analysis: {analysis}")
        return analysis

    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """Fallback analysis using simple heuristics if LLM fails."""
        query_lower = query.lower()

        # Simple keyword matching
        sources = []
        if any(word in query_lower for word in ["alert", "case", "count", "show", "list", "database", "table"]):
            sources.append("postgresql")

        if any(word in query_lower for word in ["user", "department", "engineering", "team", "api", "endpoint"]):
            if "rest_api" not in sources:
                sources.append("rest_api")

        if any(word in query_lower for word in ["customer", "payment", "account", "soap", "service"]):
            if "soap_api" not in sources:
                sources.append("soap_api")

        # Default to postgresql if nothing matched
        if not sources:
            sources = ["postgresql"]

        complexity = 3 if len(sources) == 1 else 7

        logger.info(f"📊 Fallback analysis: sources={sources}, complexity={complexity}")

        return {
            "required_sources": sources,
            "requires_consolidation": len(sources) > 1,
            "complexity": complexity,
            "query_type": "count" if "count" in query_lower else "list",
            "reasoning": "Fallback heuristic analysis"
        }

    async def _generate_steps(
        self,
        query: str,
        analysis: Dict[str, Any]
    ) -> List[ExecutionStep]:
        """Generate execution steps based on analysis."""
        steps = []
        required_sources = analysis["required_sources"]

        logger.info(f"🔨 Generating steps for {len(required_sources)} data sources...")

        # Map data source types to agent types
        source_to_agent = {
            "postgresql": AgentType.SQL_AGENT,
            "oracle": AgentType.SQL_AGENT,
            "rest_api": AgentType.API_AGENT,
            "soap_api": AgentType.SOAP_AGENT
        }

        if len(required_sources) == 1:
            # Simple single-step query
            source = required_sources[0]
            agent_type = source_to_agent.get(source, AgentType.SQL_AGENT)

            step = StateFactory.create_execution_step(
                step_id="step_1",
                agent_type=agent_type,
                description=f"Execute query using {agent_type.value}",
                parameters={"query": query},
                tool_name=None,
                depends_on=[]
            )
            steps.append(step)

            logger.info(f"✅ Created single-step plan with {agent_type.value}")

        else:
            # Multi-step query - create steps for each source
            for idx, source in enumerate(required_sources, 1):
                agent_type = source_to_agent.get(source, AgentType.SQL_AGENT)

                # Steps after first one depend on previous steps
                depends_on = [f"step_{i}" for i in range(1, idx)] if idx > 1 else []

                step = StateFactory.create_execution_step(
                    step_id=f"step_{idx}",
                    agent_type=agent_type,
                    description=f"Get data from {source} using {agent_type.value}",
                    parameters={"query": query, "source": source},
                    tool_name=None,
                    depends_on=depends_on
                )
                steps.append(step)

                logger.debug(f"  ✓ Step {idx}: {agent_type.value} (depends on: {depends_on})")

            logger.info(f"✅ Created multi-step plan with {len(steps)} steps")

        return steps
