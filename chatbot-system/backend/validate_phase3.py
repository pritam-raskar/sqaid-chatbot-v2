"""
Phase 3 Validation Script: Orchestration Layer

This script validates all Phase 3 components:
1. ExecutionPlanner - Query analysis and plan generation
2. SupervisorNode - Query routing and plan management
3. Routing Logic - Conditional routing functions
4. WorkflowBuilder - StateGraph construction
5. Integration with Phase 1 & 2
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.intelligence.orchestration.types import AgentState, AgentType, DataSourceType, ExecutionStepStatus
from app.intelligence.orchestration.state import StateFactory, StateHelper
from app.intelligence.orchestration.execution_planner import ExecutionPlanner
from app.intelligence.orchestration.supervisor_node import SupervisorNode
from app.intelligence.orchestration.routing import route_from_supervisor, route_from_agent
from app.intelligence.orchestration.workflow import WorkflowBuilder
from app.intelligence.agents.agent_registry import AgentRegistry
from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.llm.providers.anthropic_provider import AnthropicProvider


class Phase3Validator:
    """Validates Phase 3 implementation."""

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

    async def validate_execution_planner(self):
        """Validate ExecutionPlanner."""
        print("\n🔍 Validating ExecutionPlanner...")

        try:
            # Create planner
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            await llm_provider.connect()
            tool_registry = ToolRegistry()

            planner = ExecutionPlanner(llm_provider, tool_registry)
            self.log_test("ExecutionPlanner instantiation", True)

            # Test query analysis
            test_query = "Get all active alerts from the database"
            plan = await planner.create_plan(test_query, context=None)

            # Validate plan structure
            has_query = "query" in plan and plan["query"] == test_query
            self.log_test("Plan contains query", has_query, f"Query: {plan.get('query', 'MISSING')[:50]}")

            has_steps = "steps" in plan and len(plan["steps"]) > 0
            self.log_test("Plan has execution steps", has_steps, f"Steps: {len(plan.get('steps', []))}")

            has_metadata = "estimated_complexity" in plan and "requires_consolidation" in plan
            self.log_test("Plan has metadata", has_metadata)

            # Validate step structure
            if has_steps:
                first_step = plan["steps"][0]
                step_valid = all(k in first_step for k in ["step_number", "agent_type", "description", "data_source"])
                self.log_test("Step has required fields", step_valid, f"Agent: {first_step.get('agent_type')}")

        except Exception as e:
            self.log_test("ExecutionPlanner validation", False, str(e))

    async def validate_supervisor_node(self):
        """Validate SupervisorNode."""
        print("\n🔍 Validating SupervisorNode...")

        try:
            # Create supervisor
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            await llm_provider.connect()
            tool_registry = ToolRegistry()

            planner = ExecutionPlanner(llm_provider, tool_registry)
            supervisor = SupervisorNode(planner)
            self.log_test("SupervisorNode instantiation", True)

            # Test with initial state
            initial_state = StateFactory.create_initial_state(
                user_query="Get all alerts",
                session_id="test-session-123"
            )

            result = await supervisor(initial_state)

            # Validate result structure
            has_plan = "execution_plan" in result
            self.log_test("Supervisor creates execution plan", has_plan)

            has_next_agent = "next_agent" in result
            self.log_test("Supervisor sets next_agent", has_next_agent, f"Next: {result.get('next_agent')}")

        except Exception as e:
            self.log_test("SupervisorNode validation", False, str(e))

    def validate_routing_logic(self):
        """Validate routing functions."""
        print("\n🔍 Validating Routing Logic...")

        try:
            # Test route_from_supervisor
            test_state: AgentState = StateFactory.create_initial_state("test", "session-1")
            test_state["next_agent"] = AgentType.SQL_AGENT

            route = route_from_supervisor(test_state)
            self.log_test("route_from_supervisor with SQL_AGENT", route == "sql_agent", f"Route: {route}")

            # Test with API agent
            test_state["next_agent"] = AgentType.API_AGENT
            route = route_from_supervisor(test_state)
            self.log_test("route_from_supervisor with API_AGENT", route == "api_agent", f"Route: {route}")

            # Test with SOAP agent
            test_state["next_agent"] = AgentType.SOAP_AGENT
            route = route_from_supervisor(test_state)
            self.log_test("route_from_supervisor with SOAP_AGENT", route == "soap_agent", f"Route: {route}")

            # Test route_from_agent with more steps
            plan = StateFactory.create_execution_plan(
                query="test",
                steps=[
                    StateFactory.create_execution_step(1, AgentType.SQL_AGENT, "Step 1", DataSourceType.POSTGRESQL),
                    StateFactory.create_execution_step(2, AgentType.API_AGENT, "Step 2", DataSourceType.REST_API)
                ],
                estimated_complexity="medium"
            )
            test_state["execution_plan"] = plan
            test_state["current_step_index"] = 0
            StateHelper.mark_step_complete(test_state, 0, ExecutionStepStatus.COMPLETED)
            test_state["current_step_index"] = 1

            route = route_from_agent(test_state)
            self.log_test("route_from_agent with remaining steps", route == "supervisor", f"Route: {route}")

            # Test route_from_agent at last step
            StateHelper.mark_step_complete(test_state, 1, ExecutionStepStatus.COMPLETED)
            test_state["current_step_index"] = 2

            route = route_from_agent(test_state)
            self.log_test("route_from_agent at final step", route == "end", f"Route: {route}")

        except Exception as e:
            self.log_test("Routing logic validation", False, str(e))

    async def validate_workflow_builder(self):
        """Validate WorkflowBuilder."""
        print("\n🔍 Validating WorkflowBuilder...")

        try:
            # Create workflow builder
            import os
            llm_provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
            await llm_provider.connect()
            tool_registry = ToolRegistry()
            agent_registry = AgentRegistry()

            planner = ExecutionPlanner(llm_provider, tool_registry)
            supervisor = SupervisorNode(planner)
            builder = WorkflowBuilder(supervisor, agent_registry)
            self.log_test("WorkflowBuilder instantiation", True)

            # Build workflow
            workflow = builder.build()
            self.log_test("Workflow compilation", workflow is not None)

            # Verify workflow has required attributes
            has_invoke = hasattr(workflow, 'invoke') or hasattr(workflow, 'ainvoke')
            self.log_test("Workflow has invoke method", has_invoke)

        except Exception as e:
            self.log_test("WorkflowBuilder validation", False, str(e))

    def validate_integration(self):
        """Validate integration with Phase 1 & 2."""
        print("\n🔍 Validating Phase 1 & 2 Integration...")

        try:
            # Check Phase 1 components are accessible
            from app.intelligence.orchestration.types import AgentState, ExecutionPlan
            from app.intelligence.orchestration.state import StateFactory, StateHelper
            from app.intelligence.orchestration.base_node import BaseNode
            self.log_test("Phase 1 types and state accessible", True)

            # Check Phase 2 components are accessible
            from app.intelligence.agents.base_agent import BaseAgent
            from app.intelligence.agents.agent_registry import AgentRegistry
            self.log_test("Phase 2 agents accessible", True)

            # Test state creation and manipulation
            state = StateFactory.create_initial_state("test query", "session-123")
            plan = StateFactory.create_execution_plan(
                query="test",
                steps=[StateFactory.create_execution_step(1, AgentType.SQL_AGENT, "test", DataSourceType.POSTGRESQL)],
                estimated_complexity="low"
            )
            state["execution_plan"] = plan

            # Test StateHelper methods
            update = StateHelper.mark_step_complete(state, success=True)
            has_step_update = "current_step_index" in update
            self.log_test("StateHelper integration", has_step_update, "mark_step_complete works")

        except Exception as e:
            self.log_test("Integration validation", False, str(e))

    async def run_all_validations(self):
        """Run all validation tests."""
        print("=" * 60)
        print("🚀 PHASE 3 VALIDATION: ORCHESTRATION LAYER")
        print("=" * 60)

        await self.validate_execution_planner()
        await self.validate_supervisor_node()
        self.validate_routing_logic()
        await self.validate_workflow_builder()
        self.validate_integration()

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
    validator = Phase3Validator()
    success = await validator.run_all_validations()

    if success:
        print("\n✅ Phase 3 validation PASSED! Ready for Phase 4.")
        sys.exit(0)
    else:
        print("\n❌ Phase 3 validation FAILED. Please review errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
