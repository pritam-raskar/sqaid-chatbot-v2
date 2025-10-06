"""
Consolidator Node - Merges results from multiple data sources.
Uses LLM to intelligently combine and format results.
"""
import logging
from typing import Dict, Any, List, Optional
import json

from app.intelligence.orchestration.base_node import BaseNode
from app.intelligence.orchestration.types import AgentState, NodeResponse, AgentType, AgentResult
from app.intelligence.orchestration.state import StateHelper
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class ConsolidatorNode(BaseNode):
    """
    Consolidates results from multiple agents into a coherent response.

    Responsibilities:
    - Collect results from all agents (SQL, API, SOAP)
    - Merge cross-source data intelligently
    - Format final response for user
    - Handle empty or error results gracefully

    Capabilities:
    - LLM-powered data merging (understands relationships)
    - JSON/Table formatting
    - Error aggregation
    - Source attribution
    """

    def __init__(self, llm_provider: BaseLLMProvider):
        """
        Initialize consolidator node.

        Args:
            llm_provider: LLM provider for intelligent merging (supports all providers)
        """
        super().__init__(node_name="consolidator", agent_type=AgentType.CONSOLIDATOR)
        self.llm_provider = llm_provider

        logger.info("✅ ConsolidatorNode initialized")

    async def _execute(self, state: AgentState) -> NodeResponse:
        """
        Execute consolidation logic.

        Args:
            state: Current AgentState with all results

        Returns:
            NodeResponse with final_response and should_continue=False

        Flow:
            1. Collect all results from state
            2. Check if consolidation needed
            3. If yes, use LLM to merge intelligently
            4. If no, format single-source results
            5. Return formatted response
        """
        query = state.get("user_query", "")
        execution_plan = state.get("execution_plan")

        logger.info(f"🔄 Consolidating results for query: {query[:50]}...")

        # Collect all results
        sql_results = state.get("sql_results", [])
        api_results = state.get("api_results", [])
        soap_results = state.get("soap_results", [])

        total_results = len(sql_results) + len(api_results) + len(soap_results)
        logger.info(
            f"📊 Results collected: SQL={len(sql_results)}, "
            f"API={len(api_results)}, SOAP={len(soap_results)}"
        )

        # Check if consolidation is needed
        requires_consolidation = False
        if execution_plan:
            requires_consolidation = execution_plan.get("requires_consolidation", False)

        # Consolidate results
        if requires_consolidation and total_results > 1:
            logger.info("🧩 Multi-source consolidation required, using LLM...")
            final_response = await self._consolidate_with_llm(
                query=query,
                sql_results=sql_results,
                api_results=api_results,
                soap_results=soap_results,
                execution_plan=execution_plan
            )
        else:
            logger.info("📝 Simple formatting (single source or no consolidation)...")
            final_response = self._format_simple(
                sql_results=sql_results,
                api_results=api_results,
                soap_results=soap_results
            )

        logger.info(f"✅ Consolidation complete: {len(final_response)} chars")

        return {
            "final_response": final_response,
            "should_continue": False,
            "consolidation_complete": True
        }

    async def _consolidate_with_llm(
        self,
        query: str,
        sql_results: List[AgentResult],
        api_results: List[AgentResult],
        soap_results: List[AgentResult],
        execution_plan: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use LLM to intelligently merge results from multiple sources.

        Args:
            query: Original user query
            sql_results: Results from SQL agent
            api_results: Results from API agent
            soap_results: Results from SOAP agent
            execution_plan: Execution plan with consolidation hints

        Returns:
            Formatted response string

        The LLM understands:
        - Data relationships (joins, correlations)
        - What the user is asking for
        - How to present information clearly
        """
        logger.info("🤖 Using LLM for intelligent data consolidation...")

        # Build consolidation prompt
        prompt = self._build_consolidation_prompt(
            query=query,
            sql_results=sql_results,
            api_results=api_results,
            soap_results=soap_results,
            execution_plan=execution_plan
        )

        # Log the prompt
        self._log("=" * 80, level="info")
        self._log("🔀 [CONSOLIDATOR] Prompt:", level="info")
        self._log("-" * 80, level="info")
        self._log(prompt[:1000] + ("..." if len(prompt) > 1000 else ""), level="info")
        self._log("=" * 80, level="info")

        # Get model from settings
        model = None
        try:
            from app.core.config import get_settings
            settings = get_settings()
            model = settings.get_model_for_agent("consolidator")
            self._log(f"🤖 [CONSOLIDATOR] Using model: {model}", level="info")
        except Exception as e:
            logger.debug(f"Could not get model from settings: {e}")

        try:
            # Check if visualizations are enabled
            from app.core.config import get_settings
            settings = get_settings()
            enable_visualizations = getattr(settings, 'enable_visualizations', False)

            # Detect query intent
            query_lower = query.lower()
            is_list_query = any(keyword in query_lower for keyword in [
                "show me", "list", "which", "get all", "associated", "find all"
            ])

            # Build intent-aware system message
            if is_list_query:
                system_content = (
                    "You are a data consolidation assistant. The user is requesting a LIST of records.\n\n"

                    "RESPONSE STRUCTURE:\n"
                    "1. Brief intro (1 line)\n"
                    "2. Data table (4-5 most important columns: IDs, status, dates, priority)\n"
                    "3. DATA-GROUNDED ANALYSIS (REQUIRED)\n\n"

                    "=== ANALYSIS REQUIREMENTS ===\n\n"

                    "Provide analysis based strictly on observable data:\n\n"

                    "A) STATISTICAL SUMMARY:\n"
                    "   - Totals, counts, percentages from the visible data\n"
                    "   - Example: '5 alerts found, all in Open status (100%)'\n\n"

                    "B) DISTRIBUTION PATTERNS:\n"
                    "   - How values are distributed across categories\n"
                    "   - Concentrations, ranges, clusters\n"
                    "   - Example: 'Priority levels: 3 High (60%), 2 Medium (40%)'\n\n"

                    "C) NOTABLE OBSERVATIONS:\n"
                    "   - Interesting patterns, comparisons, contrasts\n"
                    "   - Example: 'All 5 alerts were created on the same date (2025-01-03)'\n\n"

                    "=== CRITICAL RESTRICTIONS ===\n\n"

                    "DO:\n"
                    "✅ Analyze only what's visible in the query results\n"
                    "✅ Calculate statistics from the data shown\n"
                    "✅ Describe patterns objectively\n"
                    "✅ Use specific numbers and percentages\n\n"

                    "DO NOT:\n"
                    "❌ Reference thresholds, SLAs, or benchmarks you don't have\n"
                    "❌ Make claims about 'normal' or 'abnormal' without data\n"
                    "❌ Suggest actions requiring unknown information\n"
                    "❌ Assume business context, rules, or policies\n"
                    "❌ Use risk/severity language without factual basis\n"
                    "❌ Mention visualizations or formatting\n\n"

                    "EXAMPLE:\n"
                    "Found 5 alerts for focal entity 3189446387:\n\n"
                    "| alert_id | status | priority | alert_type | created_at |\n"
                    "| --- | --- | --- | --- | --- |\n"
                    "| AccRev_001 | Open | High | Account Review | 2025-01-03 23:29 |\n"
                    "| AccRev_002 | Open | High | Account Review | 2025-01-03 23:29 |\n"
                    "| AccRev_003 | Open | High | Account Review | 2025-01-03 23:29 |\n"
                    "| AccRev_004 | Open | High | Account Review | 2025-01-03 23:29 |\n"
                    "| AccRev_005 | Open | High | Account Review | 2025-01-03 20:13 |\n\n"

                    "ANALYSIS:\n"
                    "• Status: All 5 alerts are in Open status (100%)\n"
                    "• Priority: All 5 alerts are High priority\n"
                    "• Type: All alerts are Account Review type\n"
                    "• Timing: 4 alerts created at 23:29, 1 alert created at 20:13 on 2025-01-03\n"
                    "• Pattern: Uniform alert characteristics across all records for this entity\n"
                )
            else:
                system_content = (
                    "You are a data consolidation assistant. "
                    "Your job is to merge results from multiple data sources into a coherent, "
                    "well-formatted response that directly answers the user's question. "
                    "Present data clearly using tables, lists, or JSON as appropriate. "
                    "If data from different sources relates to each other, join/merge it intelligently."
                )

            # Enhance with visualization instructions if enabled
            if enable_visualizations:
                try:
                    from app.prompts.visualization_prompt import VisualizationPromptBuilder
                    viz_builder = VisualizationPromptBuilder()
                    system_content = viz_builder.build_enhanced_prompt(
                        base_prompt=system_content,
                        context={'query': query}
                    )
                    logger.info("✨ Enhanced prompt with visualization instructions")
                except Exception as e:
                    logger.warning(f"Failed to enhance prompt with visualization: {e}")

            # Call LLM (works with any provider: Anthropic, OpenAI, Eliza, etc.)
            messages = [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            logger.debug(f"📤 Sending consolidation request to LLM...")

            # Prepare kwargs for model parameter
            consolidator_kwargs = {
                "temperature": 0.3,  # Slightly creative for formatting
                "max_tokens": 2000
            }
            if model:
                consolidator_kwargs["model"] = model

            response = await self.llm_provider.chat_completion(
                messages=messages,
                **consolidator_kwargs
            )

            # Extract response text (format varies by provider)
            response_text = self._extract_response_text(response)

            # Log the response
            self._log("=" * 80, level="info")
            self._log("🔀 [CONSOLIDATOR] Response:", level="info")
            self._log("-" * 80, level="info")
            self._log(response_text[:500] + ("..." if len(response_text) > 500 else ""), level="info")
            self._log("=" * 80, level="info")

            logger.info(f"✅ LLM consolidation complete: {len(response_text)} chars")
            return response_text

        except Exception as e:
            logger.error(f"❌ LLM consolidation failed: {e}")
            logger.info("🔄 Falling back to simple formatting...")
            return self._format_simple(sql_results, api_results, soap_results)

    def _build_consolidation_prompt(
        self,
        query: str,
        sql_results: List[AgentResult],
        api_results: List[AgentResult],
        soap_results: List[AgentResult],
        execution_plan: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for LLM consolidation.

        Args:
            query: User query
            sql_results: SQL results
            api_results: API results
            soap_results: SOAP results
            execution_plan: Execution plan

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"User Query: {query}",
            "",
            "Data from multiple sources:",
            ""
        ]

        # Add SQL results
        if sql_results:
            prompt_parts.append("## SQL Database Results:")
            for i, result in enumerate(sql_results, 1):
                data = result.get("data", {})
                tool = result.get("tool_name", "unknown")
                prompt_parts.append(f"### Result {i} (from {tool}):")
                prompt_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")
                prompt_parts.append("")

        # Add API results
        if api_results:
            prompt_parts.append("## REST API Results:")
            for i, result in enumerate(api_results, 1):
                data = result.get("data", {})
                tool = result.get("tool_name", "unknown")
                prompt_parts.append(f"### Result {i} (from {tool}):")
                prompt_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")
                prompt_parts.append("")

        # Add SOAP results
        if soap_results:
            prompt_parts.append("## SOAP Service Results:")
            for i, result in enumerate(soap_results, 1):
                data = result.get("data", {})
                tool = result.get("tool_name", "unknown")
                prompt_parts.append(f"### Result {i} (from {tool}):")
                prompt_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")
                prompt_parts.append("")

        # Add consolidation instructions
        prompt_parts.extend([
            "## Instructions:",
            "1. Analyze all results from different sources",
            "2. Identify relationships between data (e.g., user IDs, alert IDs)",
            "3. Merge/join data intelligently if needed",
            "4. Format the response to directly answer the user's question",
            "5. Use clear formatting (tables, lists, or JSON)",
            "6. Include source attribution where helpful",
            "7. Handle missing or error data gracefully",
            "",
            "Provide a well-formatted response:"
        ])

        return "\n".join(prompt_parts)

    def _format_simple(
        self,
        sql_results: List[AgentResult],
        api_results: List[AgentResult],
        soap_results: List[AgentResult]
    ) -> str:
        """
        Simple formatting without LLM (fallback or single-source).

        Args:
            sql_results: SQL results
            api_results: API results
            soap_results: SOAP results

        Returns:
            Formatted response string
        """
        logger.info("📋 Using simple formatting (no LLM)...")

        response_parts = []

        # Format SQL results
        if sql_results:
            response_parts.append("## Database Results:")
            for i, result in enumerate(sql_results, 1):
                data = result.get("data", {})
                error = result.get("error")
                tool = result.get("tool_name", "unknown_tool")

                if error:
                    response_parts.append(f"- Result {i} ({tool}): ❌ Error: {error}")
                else:
                    response_parts.append(f"- Result {i} ({tool}):")
                    response_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")

        # Format API results
        if api_results:
            response_parts.append("\n## API Results:")
            for i, result in enumerate(api_results, 1):
                data = result.get("data", {})
                error = result.get("error")
                tool = result.get("tool_name", "unknown_tool")

                if error:
                    response_parts.append(f"- Result {i} ({tool}): ❌ Error: {error}")
                else:
                    response_parts.append(f"- Result {i} ({tool}):")
                    response_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")

        # Format SOAP results
        if soap_results:
            response_parts.append("\n## SOAP Results:")
            for i, result in enumerate(soap_results, 1):
                data = result.get("data", {})
                error = result.get("error")
                tool = result.get("tool_name", "unknown_tool")

                if error:
                    response_parts.append(f"- Result {i} ({tool}): ❌ Error: {error}")
                else:
                    response_parts.append(f"- Result {i} ({tool}):")
                    response_parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")

        if not response_parts:
            return "No results found."

        return "\n".join(response_parts)

    def _extract_response_text(self, response: Dict[str, Any]) -> str:
        """
        Extract response text from LLM response.
        Handles different provider response formats.

        Args:
            response: Raw LLM response

        Returns:
            Extracted text content

        Provider formats:
        - Anthropic: response["content"][0]["text"]
        - OpenAI: response["choices"][0]["message"]["content"]
        - Eliza: response["message"]["content"] or response["content"]
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
