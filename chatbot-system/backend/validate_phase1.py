"""
Phase 1 Validation Script
Validates all infrastructure components are working correctly.
"""
import asyncio
import sys
from pathlib import Path

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text):
    """Print a formatted header"""
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}{text.center(70)}{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    """Print info message"""
    print(f"   {text}")

async def validate_phase1():
    """Run all Phase 1 validation checks"""

    print_header("PHASE 1: INFRASTRUCTURE VALIDATION")

    validation_passed = True

    # Test 1: Directory Structure
    print(f"{BOLD}📁 Checking Directory Structure...{RESET}")
    try:
        required_dirs = [
            "app/intelligence/orchestration",
            "app/intelligence/agents"
        ]

        for dir_path in required_dirs:
            full_path = Path(dir_path)
            if full_path.exists():
                print_success(f"Directory exists: {dir_path}")
            else:
                print_error(f"Directory missing: {dir_path}")
                validation_passed = False

        # Check __init__.py files
        init_files = [
            "app/intelligence/orchestration/__init__.py",
            "app/intelligence/agents/__init__.py"
        ]

        for init_file in init_files:
            full_path = Path(init_file)
            if full_path.exists():
                print_success(f"Init file exists: {init_file}")
            else:
                print_error(f"Init file missing: {init_file}")
                validation_passed = False

    except Exception as e:
        print_error(f"Directory validation failed: {e}")
        validation_passed = False

    # Test 2: Type Definitions
    print(f"\n{BOLD}📋 Checking Type Definitions...{RESET}")
    try:
        from app.intelligence.orchestration.types import (
            AgentState, AgentType, DataSourceType,
            ExecutionPlan, ExecutionStep, ExecutionStepStatus,
            AgentResult, NodeResponse
        )

        print_success("All type definitions imported successfully")

        # Test enum values
        assert AgentType.SUPERVISOR.value == "supervisor"
        assert AgentType.SQL_AGENT.value == "sql_agent"
        assert AgentType.API_AGENT.value == "api_agent"
        print_success("AgentType enum values are correct")

        assert DataSourceType.POSTGRESQL.value == "postgresql"
        assert DataSourceType.REST_API.value == "rest_api"
        print_success("DataSourceType enum values are correct")

        assert ExecutionStepStatus.PENDING.value == "pending"
        assert ExecutionStepStatus.COMPLETED.value == "completed"
        print_success("ExecutionStepStatus enum values are correct")

    except Exception as e:
        print_error(f"Type definitions validation failed: {e}")
        validation_passed = False

    # Test 3: State Management
    print(f"\n{BOLD}🔄 Checking State Management...{RESET}")
    try:
        from app.intelligence.orchestration.state import StateFactory, StateHelper
        from app.intelligence.orchestration.types import AgentType

        # Test StateFactory.create_initial_state
        state = StateFactory.create_initial_state("Test query", "test-session-123")

        assert state["user_query"] == "Test query"
        assert state["session_id"] == "test-session-123"
        assert state["current_step_index"] == 0
        assert state["sql_results"] == []
        assert state["should_continue"] is True
        print_success("StateFactory.create_initial_state() works correctly")

        # Test StateFactory.create_execution_step
        step = StateFactory.create_execution_step(
            step_id="step_1",
            agent_type=AgentType.SQL_AGENT,
            description="Test step",
            parameters={"test": "param"}
        )

        assert step["step_id"] == "step_1"
        assert step["agent_type"] == AgentType.SQL_AGENT
        assert step["status"] == ExecutionStepStatus.PENDING
        print_success("StateFactory.create_execution_step() works correctly")

        # Test StateHelper.add_agent_result
        result_update = StateHelper.add_agent_result(
            state=state,
            agent_type=AgentType.SQL_AGENT,
            result_data={"count": 29},
            tool_name="test_tool",
            execution_time_ms=100.0
        )

        assert "sql_results" in result_update
        assert len(result_update["sql_results"]) == 1
        print_success("StateHelper.add_agent_result() works correctly")

        # Test StateHelper.get_all_results
        test_state = state.copy()
        test_state["sql_results"] = [{"data": "sql_data"}]
        test_state["api_results"] = [{"data": "api_data"}]

        all_results = StateHelper.get_all_results(test_state)
        assert len(all_results) == 2
        print_success("StateHelper.get_all_results() works correctly")

    except Exception as e:
        print_error(f"State management validation failed: {e}")
        validation_passed = False

    # Test 4: Base Node Class
    print(f"\n{BOLD}🏗️  Checking Base Node Class...{RESET}")
    try:
        from app.intelligence.orchestration.base_node import BaseNode, PassthroughNode
        from app.intelligence.orchestration.state import StateFactory

        # Test PassthroughNode
        node = PassthroughNode()
        state = StateFactory.create_initial_state("Test query", "test-123")

        response = await node(state)

        assert isinstance(response, dict)
        assert "performance_metrics" in response
        print_success("PassthroughNode executes successfully")

        # Verify performance metrics were added
        assert "agents_called" in response["performance_metrics"]
        print_success("Performance tracking is working")

    except Exception as e:
        print_error(f"Base node validation failed: {e}")
        validation_passed = False

    # Test 5: Configuration Settings
    print(f"\n{BOLD}⚙️  Checking Configuration Settings...{RESET}")
    try:
        from app.core.config import get_settings

        settings = get_settings()

        # Check LangGraph settings exist
        assert hasattr(settings, "use_langgraph")
        assert hasattr(settings, "langgraph_enable_parallel")
        assert hasattr(settings, "langgraph_enable_caching")
        assert hasattr(settings, "langgraph_max_iterations")
        assert hasattr(settings, "langgraph_timeout")
        assert hasattr(settings, "langgraph_log_level")
        print_success("All LangGraph settings are present")

        # Check default values
        assert settings.use_langgraph is False
        assert settings.langgraph_timeout == 300
        assert settings.langgraph_max_iterations == 10
        print_success("LangGraph settings have correct default values")

        print_info(f"USE_LANGGRAPH: {settings.use_langgraph}")
        print_info(f"LANGGRAPH_TIMEOUT: {settings.langgraph_timeout}s")
        print_info(f"LANGGRAPH_MAX_ITERATIONS: {settings.langgraph_max_iterations}")
        print_info(f"LANGGRAPH_ENABLE_CACHING: {settings.langgraph_enable_caching}")

    except Exception as e:
        print_error(f"Configuration validation failed: {e}")
        validation_passed = False

    # Test 6: Dependencies
    print(f"\n{BOLD}📦 Checking Dependencies...{RESET}")
    try:
        import langgraph
        from langgraph.graph import StateGraph
        print_success("LangGraph package installed")

        from langchain_community.agent_toolkits import SQLDatabaseToolkit
        print_success("LangChain Community package installed")

        import sqlalchemy
        print_success("SQLAlchemy installed")

        from typing import TypedDict, Annotated
        print_success("Typing support available")

    except Exception as e:
        print_error(f"Dependency validation failed: {e}")
        validation_passed = False

    # Test 7: Files Created
    print(f"\n{BOLD}📄 Checking Created Files...{RESET}")
    try:
        required_files = [
            "app/intelligence/orchestration/__init__.py",
            "app/intelligence/orchestration/types.py",
            "app/intelligence/orchestration/state.py",
            "app/intelligence/orchestration/base_node.py",
            "app/intelligence/agents/__init__.py"
        ]

        for file_path in required_files:
            full_path = Path(file_path)
            if full_path.exists():
                size = full_path.stat().st_size
                print_success(f"{file_path} ({size} bytes)")
            else:
                print_error(f"File missing: {file_path}")
                validation_passed = False

    except Exception as e:
        print_error(f"File validation failed: {e}")
        validation_passed = False

    # Final Summary
    print_header("VALIDATION SUMMARY")

    if validation_passed:
        print(f"{GREEN}{BOLD}✅ ALL VALIDATIONS PASSED!{RESET}\n")
        print(f"{GREEN}Phase 1 infrastructure is ready for Phase 2 development.{RESET}\n")
        return 0
    else:
        print(f"{RED}{BOLD}❌ SOME VALIDATIONS FAILED{RESET}\n")
        print(f"{RED}Please fix the issues above before proceeding to Phase 2.{RESET}\n")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(validate_phase1())
    sys.exit(exit_code)
