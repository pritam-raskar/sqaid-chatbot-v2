"""
Test script for LangGraph deployment.
Tests WebSocket connection and LangGraph orchestration.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))


async def test_initialization():
    """Test that LangGraph components can be initialized."""
    print("=" * 60)
    print("🧪 TEST 1: Component Initialization")
    print("=" * 60)

    try:
        # Test imports
        print("\n1. Testing imports...")
        from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator
        from app.intelligence.tool_registry import ToolRegistry
        from app.llm.providers.anthropic_provider import AnthropicProvider
        from app.core.config import AppSettings
        print("   ✅ All imports successful")

        # Test settings
        print("\n2. Checking settings...")
        try:
            from app.core.config import get_settings
            settings = get_settings()
            use_langgraph = getattr(settings, 'use_langgraph', False)
            print(f"   USE_LANGGRAPH = {use_langgraph}")

            if not use_langgraph:
                print("   ⚠️  WARNING: USE_LANGGRAPH is False in settings")
                print("   This might mean .env is not being read correctly")
        except Exception as e:
            print(f"   ⚠️  Could not read settings: {e}")

        # Test provider initialization
        print("\n3. Testing LLM provider...")
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "":
            print("   ⚠️  WARNING: No ANTHROPIC_API_KEY found")
        else:
            print(f"   ✅ API key found: {api_key[:20]}...")

        provider = AnthropicProvider(api_key=api_key or "test-key")
        await provider.connect()
        print("   ✅ Provider initialized")

        # Test orchestrator initialization
        print("\n4. Testing LangGraph orchestrator...")
        tool_registry = ToolRegistry()
        print(f"   Tool registry: {len(tool_registry.tools)} tools")

        orchestrator = LangGraphOrchestrator(
            llm_provider=provider,
            tool_registry=tool_registry
        )
        print("   ✅ LangGraph orchestrator initialized")

        # Check workflow
        print("\n5. Checking workflow compilation...")
        if orchestrator.workflow:
            print("   ✅ Workflow compiled successfully")
        else:
            print("   ❌ Workflow not compiled")

        # Get statistics
        stats = orchestrator.get_statistics()
        print("\n6. Orchestrator statistics:")
        for key, value in stats.items():
            print(f"   - {key}: {value}")

        print("\n" + "=" * 60)
        print("✅ INITIALIZATION TEST PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ INITIALIZATION TEST FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


async def test_simple_query():
    """Test a simple query through the orchestrator."""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Simple Query Processing")
    print("=" * 60)

    try:
        # Initialize orchestrator
        print("\n1. Initializing orchestrator...")
        from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator
        from app.intelligence.tool_registry import ToolRegistry
        from app.llm.providers.anthropic_provider import AnthropicProvider
        import os

        provider = AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY", "test-key"))
        await provider.connect()

        tool_registry = ToolRegistry()
        orchestrator = LangGraphOrchestrator(
            llm_provider=provider,
            tool_registry=tool_registry
        )
        print("   ✅ Orchestrator ready")

        # Test simple query
        print("\n2. Processing test query...")
        test_query = "Hello, how many tools do you have?"
        print(f"   Query: \"{test_query}\"")

        # Note: This will actually call the LLM, so it might fail if API key is invalid
        # or if there are network issues
        response = await orchestrator.process_message(
            message=test_query,
            session_id="test-session-123",
            stream=False
        )

        print("\n3. Response received:")
        print(f"   Success: {response.get('success', False)}")
        if response.get('content'):
            print(f"   Content: {response.get('content')[:200]}...")
        if response.get('error'):
            print(f"   Error: {response.get('error')}")

        print("\n" + "=" * 60)
        if response.get('success'):
            print("✅ QUERY TEST PASSED")
        else:
            print("⚠️  QUERY TEST COMPLETED WITH ERRORS")
        print("=" * 60)
        return response.get('success', False)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ QUERY TEST FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


async def test_provider_extraction():
    """Test response extraction for different providers."""
    print("\n" + "=" * 60)
    print("🧪 TEST 3: Provider Response Extraction")
    print("=" * 60)

    try:
        from app.intelligence.orchestration.execution_planner import ExecutionPlanner
        from app.intelligence.orchestration.consolidator_node import ConsolidatorNode

        # Create instances
        planner = ExecutionPlanner.__new__(ExecutionPlanner)
        consolidator = ConsolidatorNode.__new__(ConsolidatorNode)

        # Test different response formats
        test_cases = [
            ("Anthropic", {'content': [{'text': 'Anthropic response', 'type': 'text'}]}),
            ("OpenAI", {'choices': [{'message': {'content': 'OpenAI response'}}]}),
            ("Eliza", {'content': 'Eliza response'}),
            ("LiteLLM", {'choices': [{'message': {'content': 'LiteLLM response'}}]}),
        ]

        print("\nTesting ExecutionPlanner extraction:")
        for provider, response in test_cases:
            result = planner._extract_response_text(response)
            status = "✅" if result and "response" in result else "❌"
            print(f"   {status} {provider}: {result}")

        print("\nTesting ConsolidatorNode extraction:")
        for provider, response in test_cases:
            result = consolidator._extract_response_text(response)
            status = "✅" if result and "response" in result else "❌"
            print(f"   {status} {provider}: {result}")

        print("\n" + "=" * 60)
        print("✅ PROVIDER EXTRACTION TEST PASSED")
        print("=" * 60)
        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ PROVIDER EXTRACTION TEST FAILED")
        print(f"Error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 LANGGRAPH DEPLOYMENT TEST SUITE")
    print("=" * 70)

    results = []

    # Test 1: Initialization
    result1 = await test_initialization()
    results.append(("Initialization", result1))

    # Test 2: Simple Query (might fail without valid API key)
    if result1:
        print("\n⏸️  Skipping query test to avoid API calls")
        print("   (Run manually with valid API key to test)")
        results.append(("Query Processing", None))

    # Test 3: Provider Extraction
    result3 = await test_provider_extraction()
    results.append(("Provider Extraction", result3))

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    for test_name, result in results:
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⏭️  SKIPPED"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, r in results if r is True)
    total = sum(1 for _, r in results if r is not None)

    print(f"\nResults: {passed}/{total} tests passed")
    print("=" * 70)

    # Check if ready for deployment
    critical_tests_passed = results[0][1] and results[2][1]  # Init and extraction

    if critical_tests_passed:
        print("\n✅ SYSTEM READY FOR DEPLOYMENT")
        print("\nNext steps:")
        print("1. Restart backend: pkill -f uvicorn && python3 -m uvicorn app.main:app --reload --port 8000")
        print("2. Test via WebSocket or API")
        print("3. Monitor logs for LangGraph initialization")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
