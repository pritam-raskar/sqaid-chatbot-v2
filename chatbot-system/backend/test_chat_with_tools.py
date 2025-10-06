#!/usr/bin/env python3
"""
Test chat endpoint with tool calling capability
Accepts user input for testing any question
"""

import asyncio
import json
import sys
import websockets

async def test_chat(question=None):
    uri = "ws://localhost:8000/ws/chat"

    # Get question from user if not provided
    if question is None:
        if len(sys.argv) > 1:
            # Question provided as command line argument
            question = ' '.join(sys.argv[1:])
        else:
            # Prompt user for question
            print("=" * 60)
            print("Chat Testing Tool - WebSocket Connection")
            print("=" * 60)
            question = input("\nEnter your question: ").strip()

            if not question:
                print("No question provided. Exiting.")
                return

    async with websockets.connect(uri) as websocket:
        print("\n✓ Connected to WebSocket")

        # Wait for connection established message
        response = await websocket.recv()
        connection_data = json.loads(response)
        print(f"✓ Connection established (Session ID: {connection_data.get('session_id', 'N/A')})")

        # Send test message
        test_message = {
            "type": "chat",
            "content": question,
            "id": "test-message"
        }

        print(f"\n📤 Sending Question: {question}")
        print("-" * 60)
        await websocket.send(json.dumps(test_message))

        # Collect all response chunks
        full_response = ""
        print("\n📥 Response:")
        print("-" * 60)

        while True:
            response = await websocket.recv()
            data = json.loads(response)

            response_type = data.get('type')

            if response_type == 'message_received':
                print("✓ Message acknowledged by server")
            elif response_type == 'stream_chunk':
                chunk = data.get('content', '')
                full_response += chunk
                print(chunk, end='', flush=True)
            elif response_type == 'stream_complete':
                print("\n" + "-" * 60)
                print("\n✓ Response complete")
                break
            elif response_type == 'error':
                print(f"\n❌ Error: {data.get('message')}")
                break

        print("\n" + "=" * 60)
        print("COMPLETE RESPONSE:")
        print("=" * 60)
        print(full_response)
        print("=" * 60)

        await websocket.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_chat())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")