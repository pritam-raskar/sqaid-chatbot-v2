"""
Simple test to see workflow events
"""
import asyncio
import sys
sys.path.insert(0, '/Users/pritam/Desktop/Data/sqaid/workspace/chatbot_v2/chatbot-system/backend')

from app.core.config import get_settings
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator
from app.intelligence.agents.agent_registry import AgentRegistry

async def main():
    print("Initializing LangGraph Orchestrator...")

    # Initialize components
    settings = get_settings()
    llm_provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model='claude-3-5-haiku-20241022'
    )
    await llm_provider.connect()

    tool_registry = ToolRegistry()
    agent_registry = AgentRegistry()

    orchestrator = LangGraphOrchestrator(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        settings=settings
    )

    print("\nStreaming workflow for query: 'how many alerts are available?'\n")
    print("="*60)

    async for event in orchestrator.stream_workflow(
        message="how many alerts are available?",
        session_id="test-session",
        context={}
    ):
        event_type = event.get('type')
        print(f"\n[{event_type}]")

        if event_type == 'node_update':
            node = event.get('node', 'unknown')
            state_update = event.get('state_update', {})
            print(f"  Node: {node}")
            print(f"  State keys: {list(state_update.keys())}")

            if 'final_response' in state_update:
                print(f"  ✅ FINAL RESPONSE FOUND:")
                print(f"     {state_update['final_response'][:200]}...")

        elif event_type == 'stream_complete':
            print("  ✅ Stream complete")

        elif event_type == 'error':
            print(f"  ❌ Error: {event.get('error')}")

    print("\n" + "="*60)
    print("Test complete")

if __name__ == "__main__":
    asyncio.run(main())
