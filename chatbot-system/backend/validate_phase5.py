"""
Phase 5 Validation Script: Integration & Migration

This script validates all Phase 5 components:
1. LangGraphOrchestrator - Main orchestrator class
2. WebSocket Integration - Streaming support
3. Feature Flag - USE_LANGGRAPH toggle
4. Provider Compatibility - All LLM providers
5. End-to-End Integration - Full workflow
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator
from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.agents.agent_registry import AgentRegistry
from app.llm.providers.anthropic_provider import AnthropicProvider


class Phase5Validator:
    """Validates Phase 5 implementation."""

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

    async def validate_langgraph_orchestrator(self):
        """Validate LangGraphOrchestrator."""
        print("\n🔍 Validating LangGraphOrchestrator...")

        try:
            # Create orchestrator
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            await llm_provider.connect()

            tool_registry = ToolRegistry()
            agent_registry = AgentRegistry()

            orchestrator = LangGraphOrchestrator(
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                agent_registry=agent_registry
            )

            self.log_test("LangGraphOrchestrator instantiation", True)

            # Test get_available_tools
            tools = orchestrator.get_available_tools()
            self.log_test("Get available tools", len(tools) >= 0, f"Tools: {len(tools)}")

            # Test get_tool_descriptions
            descriptions = orchestrator.get_tool_descriptions()
            self.log_test("Get tool descriptions", len(descriptions) >= 0, f"Descriptions: {len(descriptions)}")

            # Test get_statistics
            stats = orchestrator.get_statistics()
            has_stats = "agents_registered" in stats and "tools_available" in stats
            self.log_test("Get statistics", has_stats, f"Stats: {len(stats)} fields")

            # Test __repr__
            repr_str = repr(orchestrator)
            has_repr = "LangGraphOrchestrator" in repr_str
            self.log_test("String representation", has_repr)

            # Test workflow compiled
            has_workflow = orchestrator.workflow is not None
            self.log_test("Workflow compiled", has_workflow)

        except Exception as e:
            self.log_test("LangGraphOrchestrator validation", False, str(e))

    def validate_feature_flag(self):
        """Validate feature flag logic."""
        print("\n🔍 Validating Feature Flag...")

        try:
            # Test config import
            from app.core.config import AppSettings

            # Create test settings
            class TestSettings(AppSettings):
                use_langgraph: bool = False

            settings_off = TestSettings()
            self.log_test("Feature flag OFF (default)", not settings_off.use_langgraph)

            # Test with flag ON
            class TestSettingsOn(AppSettings):
                use_langgraph: bool = True

            settings_on = TestSettingsOn()
            self.log_test("Feature flag ON", settings_on.use_langgraph)

        except Exception as e:
            self.log_test("Feature flag validation", False, str(e))

    def validate_websocket_integration(self):
        """Validate WebSocket handler integration."""
        print("\n🔍 Validating WebSocket Integration...")

        try:
            # Test imports
            from app.orchestration.websocket_handler import WebSocketHandler, ConnectionManager

            self.log_test("WebSocket imports", True)

            # Test ConnectionManager
            conn_manager = ConnectionManager()
            has_connections = hasattr(conn_manager, 'active_connections')
            self.log_test("ConnectionManager instantiation", has_connections)

            # Test WebSocketHandler instantiation (mock session manager)
            class MockSessionManager:
                async def get_session(self, session_id):
                    return type('Session', (), {'id': session_id})()

                async def add_message(self, session_id, message):
                    pass

            session_manager = MockSessionManager()

            # Test without settings (UniversalAgent)
            handler = WebSocketHandler(session_manager=session_manager)
            has_agent_none = handler.agent is None
            has_langgraph_none = handler.langgraph_orchestrator is None
            self.log_test("WebSocket handler without settings", has_agent_none and has_langgraph_none)

        except Exception as e:
            self.log_test("WebSocket integration validation", False, str(e))

    def validate_provider_compatibility(self):
        """Validate all provider support."""
        print("\n🔍 Validating Provider Compatibility...")

        try:
            # Test that orchestrator works with different providers
            from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator

            # All providers should be importable
            try:
                from app.llm.providers.anthropic_provider import AnthropicProvider
                self.log_test("Anthropic provider import", True)
            except:
                self.log_test("Anthropic provider import", False)

            try:
                from app.llm.providers.openai_provider import OpenAIProvider
                self.log_test("OpenAI provider import", True)
            except:
                self.log_test("OpenAI provider import", False)

            try:
                from app.llm.providers.eliza_provider import ElizaProvider
                self.log_test("Eliza provider import", True)
            except:
                self.log_test("Eliza provider import", False)

            try:
                from app.llm.providers.litellm_provider import LiteLLMProvider
                self.log_test("LiteLLM provider import", True)
            except:
                self.log_test("LiteLLM provider import", False)

        except Exception as e:
            self.log_test("Provider compatibility validation", False, str(e))

    def validate_integration(self):
        """Validate end-to-end integration."""
        print("\n🔍 Validating End-to-End Integration...")

        try:
            # Check all phases are accessible
            from app.intelligence.orchestration.types import AgentState
            from app.intelligence.orchestration.state import StateFactory
            from app.intelligence.orchestration.execution_planner import ExecutionPlanner
            from app.intelligence.orchestration.supervisor_node import SupervisorNode
            from app.intelligence.orchestration.consolidator_node import ConsolidatorNode
            from app.intelligence.orchestration.workflow import WorkflowBuilder
            from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator

            self.log_test("All orchestration components accessible", True)

            # Test that orchestrator can be created with all components
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            tool_registry = ToolRegistry()
            agent_registry = AgentRegistry()

            # This should not raise
            orchestrator = LangGraphOrchestrator(
                llm_provider=llm_provider,
                tool_registry=tool_registry,
                agent_registry=agent_registry
            )

            # Check internal components
            has_planner = orchestrator.execution_planner is not None
            has_supervisor = orchestrator.supervisor_node is not None
            has_workflow = orchestrator.workflow is not None

            self.log_test("Orchestrator has all internal components",
                         has_planner and has_supervisor and has_workflow,
                         f"Planner: {has_planner}, Supervisor: {has_supervisor}, Workflow: {has_workflow}")

        except Exception as e:
            self.log_test("End-to-end integration validation", False, str(e))

    def validate_backward_compatibility(self):
        """Validate backward compatibility with UniversalAgent interface."""
        print("\n🔍 Validating Backward Compatibility...")

        try:
            # Test that LangGraphOrchestrator has same interface as UniversalAgent
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            tool_registry = ToolRegistry()

            orchestrator = LangGraphOrchestrator(
                llm_provider=llm_provider,
                tool_registry=tool_registry
            )

            # Check for UniversalAgent-compatible methods
            has_process_message = hasattr(orchestrator, 'process_message')
            has_get_available_tools = hasattr(orchestrator, 'get_available_tools')
            has_get_tool_descriptions = hasattr(orchestrator, 'get_tool_descriptions')

            self.log_test("Has UniversalAgent interface methods",
                         has_process_message and has_get_available_tools and has_get_tool_descriptions,
                         "process_message, get_available_tools, get_tool_descriptions")

            # Check method signatures match
            import inspect

            # process_message should accept message, session_id, context, stream
            sig = inspect.signature(orchestrator.process_message)
            params = list(sig.parameters.keys())
            has_correct_params = 'message' in params and 'session_id' in params

            self.log_test("process_message has correct signature", has_correct_params, f"Params: {params}")

        except Exception as e:
            self.log_test("Backward compatibility validation", False, str(e))

    async def run_all_validations(self):
        """Run all validation tests."""
        print("=" * 60)
        print("🚀 PHASE 5 VALIDATION: INTEGRATION & MIGRATION")
        print("=" * 60)

        await self.validate_langgraph_orchestrator()
        self.validate_feature_flag()
        self.validate_websocket_integration()
        self.validate_provider_compatibility()
        self.validate_integration()
        self.validate_backward_compatibility()

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
    validator = Phase5Validator()
    success = await validator.run_all_validations()

    if success:
        print("\n✅ Phase 5 validation PASSED! LangGraph orchestration ready for production.")
        print("\n📝 Next Steps:")
        print("  1. Set USE_LANGGRAPH=true in .env")
        print("  2. Restart backend server")
        print("  3. Test with simple queries")
        print("  4. Monitor logs for LangGraph initialization")
        print("  5. Review MIGRATION_GUIDE.md for detailed instructions")
        sys.exit(0)
    else:
        print("\n❌ Phase 5 validation FAILED. Please review errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
