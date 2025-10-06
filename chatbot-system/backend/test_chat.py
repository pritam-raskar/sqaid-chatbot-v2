"""
Test WebSocket chat endpoint with real query
"""
import asyncio
import websockets
import json
import sys

async def test_chat():
    """Test chat with question: How many alerts do we have?"""

    uri = "ws://localhost:8000/ws/chat"

    print("=" * 60)
    print("Testing Chat Endpoint")
    print("=" * 60)
    print(f"Connecting to: {uri}")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            print()

            # Wait for connection_established message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"✓ Received: {welcome_data.get('type')}")
            session_id = welcome_data.get('session_id')
            print(f"  Session ID: {session_id}")
            print()

            # Send the question
            question = "How many alerts do we have?"
            message = {
                "type": "chat",
                "content": question
            }

            print(f"Sending question: {question}")
            await websocket.send(json.dumps(message))
            print("✓ Question sent")
            print()

            print("Waiting for response...")
            print("-" * 60)

            # Receive responses
            response_count = 0
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=90.0)
                    response_count += 1

                    # Parse response
                    try:
                        data = json.loads(response)
                        msg_type = data.get('type', 'unknown')

                        print(f"\n[Response {response_count}] Type: {msg_type}")

                        if msg_type == 'status':
                            print(f"  Status: {data.get('status')}")

                        elif msg_type == 'content':
                            print(f"  Content: {data.get('content')}")

                        elif msg_type == 'error':
                            print(f"  Error: {data.get('error')}")

                        elif msg_type == 'tool_use':
                            print(f"  Tool: {data.get('tool_name')}")
                            print(f"  Input: {data.get('tool_input')}")

                        elif msg_type == 'tool_result':
                            result = data.get('result', '')
                            print(f"  Tool Result: {result[:200]}...")

                        elif msg_type == 'final':
                            print(f"  Final Response: {data.get('content')}")
                            print("\n" + "=" * 60)
                            print("✓ Conversation completed")
                            print("=" * 60)
                            break

                        else:
                            print(f"  Data: {json.dumps(data, indent=2)}")

                    except json.JSONDecodeError:
                        print(f"  Raw: {response}")

                except asyncio.TimeoutError:
                    print("\n✗ Timeout waiting for response")
                    break

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(test_chat()))
