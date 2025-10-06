#!/usr/bin/env python3
"""
Simple test client for LangGraph Multi-Agent Orchestration
Usage: python test_query.py "your question here"
"""
import asyncio
import json
import sys
import websockets


async def test_query(question: str):
    """
    Send a query to the LangGraph system and print the response.

    Args:
        question: The question to ask the system
    """
    uri = "ws://localhost:8000/ws/chat"

    print("🤖 LangGraph Multi-Agent Orchestration")
    print("="*70)
    print(f"📝 Query: {question}")
    print("="*70 + "\n")

    try:
        async with websockets.connect(uri) as websocket:
            # Wait for connection confirmation
            await websocket.recv()

            # Send query
            await websocket.send(json.dumps({
                "type": "chat",
                "content": question
            }))

            print("💬 Response:")
            print("-"*70)

            # Receive response chunks
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=120.0)
                    data = json.loads(response)
                    msg_type = data.get("type", "")

                    if msg_type == "stream_chunk":
                        # Print response chunks as they arrive
                        print(data.get("content", ""), end='', flush=True)

                    elif msg_type == "stream_complete":
                        # Query completed successfully
                        print("\n" + "-"*70)
                        print("✅ Query completed successfully!")
                        break

                    elif msg_type == "error":
                        # Error occurred
                        print(f"\n❌ Error: {data.get('error', 'Unknown error')}")
                        print("-"*70)
                        break

                except asyncio.TimeoutError:
                    print("\n⏱️ Timeout - no response received after 30 seconds")
                    print("-"*70)
                    break

                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed")
                    print("-"*70)
                    break

    except ConnectionRefusedError:
        print("❌ Error: Could not connect to backend server at ws://localhost:8000")
        print("   Make sure the backend is running on port 8000")
        return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_query.py \"your question here\"")
        print("\nExamples:")
        print('  python test_query.py "how many alerts are available?"')
        print('  python test_query.py "Give me number of alerts for each alert_type_id"')
        print('  python test_query.py "show me list of Open alerts which has score less than 90"')
        sys.exit(1)

    question = " ".join(sys.argv[1:])

    exit_code = asyncio.run(test_query(question))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
