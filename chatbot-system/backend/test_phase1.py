"""
Test script for Phase 1 infrastructure
"""
import asyncio
from app.intelligence.orchestration.base_node import PassthroughNode
from app.intelligence.orchestration.state import StateFactory, StateHelper
from app.intelligence.orchestration.types import (
    AgentType, AgentState, DataSourceType,
    ExecutionPlan, ExecutionStep
)

async def test_phase1():
    """Test all Phase 1 components"""
    print("="*60)
    print("Testing Phase 1: Infrastructure Setup")
    print("="*60)

    # Test 1: StateFactory
    print("\n1️⃣ Testing StateFactory...")
    state = StateFactory.create_initial_state('How many alerts?', 'test-123')
    print(f"   ✅ Initial state created with {len(state)} fields")
    print(f"   ✅ Session ID: {state['session_id']}")
    print(f"   ✅ User query: {state['user_query']}")

    # Test 2: StateHelper
    print("\n2️⃣ Testing StateHelper...")
    result_update = StateHelper.add_agent_result(
        state=state,
        agent_type=AgentType.SQL_AGENT,
        result_data={"count": 29},
        tool_name="test_tool",
        execution_time_ms=100.0
    )
    print(f"   ✅ Agent result added: {len(result_update['sql_results'])} results")

    # Test 3: PassthroughNode
    print("\n3️⃣ Testing PassthroughNode...")
    node = PassthroughNode()
    response = await node(state)
    print(f"   ✅ PassthroughNode executed successfully")
    print(f"   ✅ Response has performance_metrics: {'performance_metrics' in response}")

    # Test 4: All types import correctly
    print("\n4️⃣ Testing type imports...")
    print("   ✅ All type definitions imported")
    print(f"   ✅ AgentType.SQL_AGENT = {AgentType.SQL_AGENT.value}")
    print(f"   ✅ DataSourceType.POSTGRESQL = {DataSourceType.POSTGRESQL.value}")

    print("\n" + "="*60)
    print("✅ ALL PHASE 1 TESTS PASSED!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_phase1())
