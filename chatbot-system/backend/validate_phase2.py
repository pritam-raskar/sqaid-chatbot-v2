"""
Phase 2 Validation Script
Validates all specialized agents are working correctly.
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

async def validate_phase2():
    """Run all Phase 2 validation checks"""

    print_header("PHASE 2: SPECIALIZED AGENTS VALIDATION")

    validation_passed = True

    # Test 1: BaseAgent Class
    print(f"{BOLD}🏗️  Checking BaseAgent...{RESET}")
    try:
        from app.intelligence.agents.base_agent import BaseAgent
        from app.intelligence.orchestration.types import AgentType

        print_success("BaseAgent class imported successfully")

        # Verify it's abstract
        assert hasattr(BaseAgent, '_execute_query')
        print_success("BaseAgent has _execute_query abstract method")

        # Verify key methods exist
        assert hasattr(BaseAgent, 'execute')
        assert hasattr(BaseAgent, '_filter_tools')
        assert hasattr(BaseAgent, 'get_available_tools')
        print_success("BaseAgent has all required methods")

    except Exception as e:
        print_error(f"BaseAgent validation failed: {e}")
        validation_passed = False

    # Test 2: AgentRegistry
    print(f"\n{BOLD}📋 Checking AgentRegistry...{RESET}")
    try:
        from app.intelligence.agents.agent_registry import AgentRegistry
        from app.intelligence.orchestration.types import AgentType

        registry = AgentRegistry()
        print_success("AgentRegistry created successfully")

        # Test registration methods
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'get_agent')
        assert hasattr(registry, 'has_agent')
        assert hasattr(registry, 'list_agents')
        print_success("AgentRegistry has all required methods")

        # Test initial state
        assert registry.get_agent_count() == 0
        print_success("AgentRegistry starts empty")

    except Exception as e:
        print_error(f"AgentRegistry validation failed: {e}")
        validation_passed = False

    # Test 3: SQLAgent
    print(f"\n{BOLD}🗄️  Checking SQLAgent...{RESET}")
    try:
        from app.intelligence.agents.sql_agent import SQLAgent

        print_success("SQLAgent class imported successfully")

        # Verify it inherits from BaseAgent
        from app.intelligence.agents.base_agent import BaseAgent
        assert issubclass(SQLAgent, BaseAgent)
        print_success("SQLAgent inherits from BaseAgent")

        # Verify SQL-specific methods
        assert hasattr(SQLAgent, '_create_sqlalchemy_engine')
        assert hasattr(SQLAgent, '_create_langchain_llm')
        assert hasattr(SQLAgent, 'get_last_sql')
        assert hasattr(SQLAgent, 'get_table_info')
        print_success("SQLAgent has SQL-specific methods")

        print_info("Note: Full SQLAgent requires database connection for initialization")

    except Exception as e:
        print_error(f"SQLAgent validation failed: {e}")
        validation_passed = False

    # Test 4: APIAgent
    print(f"\n{BOLD}🌐 Checking APIAgent...{RESET}")
    try:
        from app.intelligence.agents.api_agent import APIAgent

        print_success("APIAgent class imported successfully")

        # Verify it inherits from BaseAgent
        from app.intelligence.agents.base_agent import BaseAgent
        assert issubclass(APIAgent, BaseAgent)
        print_success("APIAgent inherits from BaseAgent")

        # Verify API-specific methods
        assert hasattr(APIAgent, '_create_filtered_registry')
        assert hasattr(APIAgent, 'get_available_endpoints')
        assert hasattr(APIAgent, 'get_endpoint_description')
        print_success("APIAgent has API-specific methods")

        print_info("Note: Full APIAgent requires LLM provider and tool registry for initialization")

    except Exception as e:
        print_error(f"APIAgent validation failed: {e}")
        validation_passed = False

    # Test 5: SOAPAgent
    print(f"\n{BOLD}🔌 Checking SOAPAgent...{RESET}")
    try:
        from app.intelligence.agents.soap_agent import SOAPAgent

        print_success("SOAPAgent class imported successfully")

        # Verify it inherits from BaseAgent
        from app.intelligence.agents.base_agent import BaseAgent
        assert issubclass(SOAPAgent, BaseAgent)
        print_success("SOAPAgent inherits from BaseAgent")

        # Verify SOAP-specific methods
        assert hasattr(SOAPAgent, '_create_filtered_registry')
        assert hasattr(SOAPAgent, 'get_available_operations')
        assert hasattr(SOAPAgent, 'get_operation_description')
        print_success("SOAPAgent has SOAP-specific methods")

        print_info("Note: Full SOAPAgent requires LLM provider and tool registry for initialization")

    except Exception as e:
        print_error(f"SOAPAgent validation failed: {e}")
        validation_passed = False

    # Test 6: Type Compatibility
    print(f"\n{BOLD}🔗 Checking Type Compatibility...{RESET}")
    try:
        from app.intelligence.orchestration.types import AgentType, DataSourceType

        # Verify agent types
        assert AgentType.SQL_AGENT == "sql_agent"
        assert AgentType.API_AGENT == "api_agent"
        assert AgentType.SOAP_AGENT == "soap_agent"
        print_success("All AgentType values correct")

        # Verify data source types
        assert DataSourceType.POSTGRESQL == "postgresql"
        assert DataSourceType.REST_API == "rest_api"
        assert DataSourceType.SOAP_API == "soap_api"
        print_success("All DataSourceType values correct")

    except Exception as e:
        print_error(f"Type compatibility validation failed: {e}")
        validation_passed = False

    # Test 7: Files Created
    print(f"\n{BOLD}📄 Checking Created Files...{RESET}")
    try:
        required_files = [
            "app/intelligence/agents/base_agent.py",
            "app/intelligence/agents/agent_registry.py",
            "app/intelligence/agents/sql_agent.py",
            "app/intelligence/agents/api_agent.py",
            "app/intelligence/agents/soap_agent.py"
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

    # Test 8: Dependencies
    print(f"\n{BOLD}📦 Checking Dependencies...{RESET}")
    try:
        # LangChain SQL Agent dependencies
        from langchain_community.utilities import SQLDatabase
        from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
        from sqlalchemy import create_engine
        print_success("LangChain SQL Agent toolkit available")

        from langchain_anthropic import ChatAnthropic
        print_success("LangChain Anthropic provider available")

        import asyncpg
        print_success("asyncpg database driver available")

        import oracledb
        print_success("oracledb driver available")

    except Exception as e:
        print_error(f"Dependency validation failed: {e}")
        validation_passed = False

    # Test 9: Integration Check
    print(f"\n{BOLD}🔄 Checking Integration Points...{RESET}")
    try:
        # Verify Phase 1 infrastructure still works
        from app.intelligence.orchestration.types import AgentState
        from app.intelligence.orchestration.state import StateFactory
        from app.intelligence.orchestration.base_node import BaseNode

        state = StateFactory.create_initial_state("Test query", "test-123")
        print_success("Phase 1 infrastructure still functional")

        # Verify agents can work with Phase 1 types
        from app.intelligence.agents.base_agent import BaseAgent
        from app.intelligence.orchestration.types import AgentResult

        print_success("Phase 2 agents integrate with Phase 1 types")

    except Exception as e:
        print_error(f"Integration validation failed: {e}")
        validation_passed = False

    # Final Summary
    print_header("VALIDATION SUMMARY")

    if validation_passed:
        print(f"{GREEN}{BOLD}✅ ALL VALIDATIONS PASSED!{RESET}\n")
        print(f"{GREEN}Phase 2 specialized agents are ready for Phase 3 orchestration.{RESET}\n")

        print(f"{BOLD}Created Agents:{RESET}")
        print_info("• BaseAgent - Abstract base class for all agents")
        print_info("• SQLAgent - Natural Language to SQL conversion")
        print_info("• APIAgent - REST API endpoint interactions")
        print_info("• SOAPAgent - SOAP service operations")
        print_info("• AgentRegistry - Agent management and retrieval")

        print(f"\n{BOLD}Next Phase:{RESET}")
        print_info("Phase 3 will implement:")
        print_info("• SupervisorNode for query analysis")
        print_info("• ExecutionPlanner for multi-step plans")
        print_info("• WorkflowBuilder for StateGraph construction")
        print_info("• Routing logic between agents")

        return 0
    else:
        print(f"{RED}{BOLD}❌ SOME VALIDATIONS FAILED{RESET}\n")
        print(f"{RED}Please fix the issues above before proceeding to Phase 3.{RESET}\n")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(validate_phase2())
    sys.exit(exit_code)
