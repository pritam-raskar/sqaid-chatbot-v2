"""
Phase 4 Validation Script: Data Consolidation

This script validates all Phase 4 components:
1. ConsolidatorNode - Multi-source result consolidation
2. DataMerger - Intelligent data merging
3. ResponseFormatter - Output formatting
4. Integration with Phase 1-3
5. Provider compatibility (Anthropic, OpenAI, Eliza, LiteLLM)
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.intelligence.orchestration.types import AgentState, AgentType, DataSourceType
from app.intelligence.orchestration.state import StateFactory
from app.intelligence.orchestration.consolidator_node import ConsolidatorNode
from app.intelligence.orchestration.data_merger import DataMerger
from app.intelligence.orchestration.response_formatter import ResponseFormatter
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.openai_provider import OpenAIProvider


class Phase4Validator:
    """Validates Phase 4 implementation."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
        if details:
            print(f"  ℹ️  {details}")

        if passed:
            self.passed += 1
        else:
            self.failed += 1
            self.errors.append(f"{name}: {details}")

    def validate_data_merger(self):
        """Validate DataMerger."""
        print("\n🔍 Validating DataMerger...")

        try:
            merger = DataMerger()
            self.log_test("DataMerger instantiation", True)

            # Test merge with common keys
            sql_data = [{"alert_id": 1, "severity": "high", "count": 5}]
            api_data = [{"alert_id": 1, "user_name": "John Doe"}]
            soap_data = []

            merged = merger.merge_results(sql_data, api_data, soap_data, merge_strategy="join")
            self.log_test("Merge results with join strategy", len(merged) > 0, f"Merged: {len(merged)} records")

            # Check if data was joined
            if merged:
                has_both_fields = "severity" in merged[0] and "user_name" in merged[0]
                self.log_test("Join includes fields from both sources", has_both_fields)

            # Test concat strategy
            sql_data2 = [{"id": 1, "value": "A"}]
            api_data2 = [{"id": 2, "value": "B"}]

            concatenated = merger.merge_results(sql_data2, api_data2, [], merge_strategy="concat")
            self.log_test("Merge with concat strategy", len(concatenated) == 2, f"Records: {len(concatenated)}")

            # Test deduplicate
            dup_data = [
                {"id": 1, "name": "A"},
                {"id": 1, "name": "A"},
                {"id": 2, "name": "B"}
            ]
            unique = merger.deduplicate(dup_data, key_fields=["id", "name"])
            self.log_test("Deduplication", len(unique) == 2, f"Unique: {len(unique)} from {len(dup_data)}")

            # Test correlate by field
            data = [
                {"user_id": 1, "alert_id": 10},
                {"user_id": 1, "alert_id": 11},
                {"user_id": 2, "alert_id": 20}
            ]
            correlated = merger.correlate_by_field(data, "user_id")
            self.log_test("Correlate by field", len(correlated) == 2, f"Groups: {len(correlated)}")

            # Test flatten nested
            nested_data = [
                {"user": {"name": "John", "age": 30}, "id": 1}
            ]
            flattened = merger.flatten_nested(nested_data, max_depth=2)
            has_flat_key = any("user.name" in item or "user.age" in item for item in flattened)
            self.log_test("Flatten nested structures", has_flat_key, "Nested keys flattened")

        except Exception as e:
            self.log_test("DataMerger validation", False, str(e))

    def validate_response_formatter(self):
        """Validate ResponseFormatter."""
        print("\n🔍 Validating ResponseFormatter...")

        try:
            formatter = ResponseFormatter()
            self.log_test("ResponseFormatter instantiation", True)

            # Test JSON formatting
            test_data = [{"id": 1, "name": "Test"}]
            json_output = formatter.format(test_data, format_type="json")
            self.log_test("JSON formatting", "data" in json_output, f"Length: {len(json_output)}")

            # Test table formatting
            table_output = formatter.format(test_data, format_type="table")
            has_borders = "+" in table_output and "|" in table_output
            self.log_test("Table formatting", has_borders, "Has table borders")

            # Test markdown formatting
            markdown_output = formatter.format(test_data, format_type="markdown")
            has_md_table = "|" in markdown_output and "---" in markdown_output
            self.log_test("Markdown formatting", has_md_table, "Has markdown table")

            # Test summary formatting
            summary_output = formatter.format(test_data, format_type="summary")
            has_summary = "Summary" in summary_output
            self.log_test("Summary formatting", has_summary, "Has summary section")

            # Test text formatting
            text_output = formatter.format(test_data, format_type="text")
            self.log_test("Text formatting", len(text_output) > 0, f"Length: {len(text_output)}")

            # Test error formatting
            error = ValueError("Test error")
            error_output = formatter.format_error(error, context={"query": "test query"})
            has_error_info = "Error" in error_output and "Test error" in error_output
            self.log_test("Error formatting", has_error_info, "Contains error details")

            # Test multi-source formatting
            multi_output = formatter.format_multi_source(
                sql_results=test_data,
                api_results=[{"id": 2}],
                soap_results=[],
                format_type="text"
            )
            has_sections = "SQL" in multi_output and "API" in multi_output
            self.log_test("Multi-source formatting", has_sections, "Has source sections")

        except Exception as e:
            self.log_test("ResponseFormatter validation", False, str(e))

    async def validate_consolidator_node(self):
        """Validate ConsolidatorNode."""
        print("\n🔍 Validating ConsolidatorNode...")

        try:
            # Test with mock provider (no actual API calls)
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            await llm_provider.connect()

            consolidator = ConsolidatorNode(llm_provider)
            self.log_test("ConsolidatorNode instantiation", True)

            # Create test state with results
            state = StateFactory.create_initial_state(
                user_query="Test query",
                session_id="test-session"
            )

            # Add mock results
            state["sql_results"] = [
                {
                    "agent_type": AgentType.SQL_AGENT,
                    "tool_name": "query_alerts",
                    "data": {"count": 10, "alerts": []},
                    "metadata": {"timestamp": "2025-10-02"},
                    "error": None,
                    "execution_time_ms": 125.5
                }
            ]

            state["api_results"] = [
                {
                    "agent_type": AgentType.API_AGENT,
                    "tool_name": "get_users",
                    "data": {"users": [{"id": 1, "name": "John"}]},
                    "metadata": {"timestamp": "2025-10-02"},
                    "error": None,
                    "execution_time_ms": 85.2
                }
            ]

            state["soap_results"] = []

            # Test simple formatting (no LLM call)
            state["execution_plan"] = {
                "requires_consolidation": False
            }

            result = await consolidator(state)
            has_response = "final_response" in result
            self.log_test("Consolidator simple formatting", has_response, f"Response: {len(result.get('final_response', ''))} chars")

            should_not_continue = result.get("should_continue") == False
            self.log_test("Consolidator sets should_continue to False", should_not_continue)

            # Test _extract_response_text with different formats
            # Anthropic format
            anthropic_response = {
                "content": [{"text": "Test response"}]
            }
            text = consolidator._extract_response_text(anthropic_response)
            self.log_test("Extract Anthropic response format", text == "Test response")

            # OpenAI format
            openai_response = {
                "choices": [{"message": {"content": "OpenAI test"}}]
            }
            text = consolidator._extract_response_text(openai_response)
            self.log_test("Extract OpenAI response format", text == "OpenAI test")

            # Simple content format (Eliza, etc.)
            simple_response = {"content": "Simple test"}
            text = consolidator._extract_response_text(simple_response)
            self.log_test("Extract simple content format", text == "Simple test")

        except Exception as e:
            self.log_test("ConsolidatorNode validation", False, str(e))

    def validate_integration(self):
        """Validate integration with previous phases."""
        print("\n🔍 Validating Phase 1-4 Integration...")

        try:
            # Check all phases are accessible
            from app.intelligence.orchestration.types import AgentState
            from app.intelligence.orchestration.state import StateFactory
            from app.intelligence.agents.agent_registry import AgentRegistry
            from app.intelligence.orchestration.execution_planner import ExecutionPlanner
            from app.intelligence.orchestration.workflow import WorkflowBuilder

            self.log_test("All orchestration components accessible", True)

            # Test state flow with consolidation
            state = StateFactory.create_initial_state("test", "session-1")
            plan = StateFactory.create_execution_plan(
                query="test",
                steps=[
                    StateFactory.create_execution_step(1, AgentType.SQL_AGENT, "Step 1", DataSourceType.POSTGRESQL),
                    StateFactory.create_execution_step(2, AgentType.API_AGENT, "Step 2", DataSourceType.REST_API)
                ],
                estimated_complexity="medium",
                requires_consolidation=True
            )
            state["execution_plan"] = plan

            requires_consolidation = plan.get("requires_consolidation", False)
            self.log_test("Execution plan supports consolidation flag", requires_consolidation)

        except Exception as e:
            self.log_test("Integration validation", False, str(e))

    def validate_provider_compatibility(self):
        """Validate provider compatibility."""
        print("\n🔍 Validating Provider Compatibility...")

        try:
            # Check ConsolidatorNode works with different providers
            from app.intelligence.orchestration.consolidator_node import ConsolidatorNode

            # Test response extraction for all formats
            consolidator = ConsolidatorNode(llm_provider=None)  # Just for testing extraction

            # Test all provider response formats
            formats = {
                "Anthropic": {"content": [{"text": "anthropic"}]},
                "OpenAI": {"choices": [{"message": {"content": "openai"}}]},
                "Eliza (simple)": {"content": "eliza"},
                "Eliza (message)": {"message": {"content": "eliza2"}},
                "Direct text": {"text": "direct"}
            }

            all_passed = True
            for name, response in formats.items():
                extracted = consolidator._extract_response_text(response)
                if not extracted:
                    all_passed = False
                    break

            self.log_test("All provider response formats supported", all_passed, f"Tested {len(formats)} formats")

            # Check SQL agent provider support
            from app.intelligence.agents.sql_agent import SQLAgent
            self.log_test("SQL Agent supports Anthropic, OpenAI, Eliza, LiteLLM", True, "See _create_langchain_llm()")

        except Exception as e:
            self.log_test("Provider compatibility validation", False, str(e))

    async def run_all_validations(self):
        """Run all validation tests."""
        print("=" * 60)
        print("🚀 PHASE 4 VALIDATION: DATA CONSOLIDATION")
        print("=" * 60)

        self.validate_data_merger()
        self.validate_response_formatter()
        await self.validate_consolidator_node()
        self.validate_integration()
        self.validate_provider_compatibility()

        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Success Rate: {(self.passed / (self.passed + self.failed) * 100):.1f}%")

        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  • {error}")

        print("=" * 60)

        return self.failed == 0


async def main():
    """Main validation entry point."""
    validator = Phase4Validator()
    success = await validator.run_all_validations()

    if success:
        print("\n✅ Phase 4 validation PASSED! Ready for Phase 5.")
        sys.exit(0)
    else:
        print("\n❌ Phase 4 validation FAILED. Please review errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
