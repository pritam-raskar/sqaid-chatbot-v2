#!/usr/bin/env python3
"""
Test script to verify context-aware chat functionality.
Tests that follow-up questions understand previous conversation context.
"""

import asyncio
import websockets
import json
import uuid

# Configuration
WEBSOCKET_URL = "ws://localhost:8000/ws/chat"
SESSION_ID = str(uuid.uuid4())

async def test_context_aware_chat():
    """Test context-aware conversation with follow-up questions."""

    print("=" * 80)
    print("CONTEXT-AWARE CHAT TEST")
    print("=" * 80)
    print(f"Session ID: {SESSION_ID}\n")

    # Connect to WebSocket
    uri = f"{WEBSOCKET_URL}?session_id={SESSION_ID}"
    print(f"Connecting to: {uri}")

    async with websockets.connect(uri) as websocket:
        # Wait for connection confirmation
        welcome = await websocket.recv()
        welcome_msg = json.loads(welcome)
        print(f"✅ Connected: {welcome_msg.get('type')}\n")

        # Test Case 1: First question (establishes context)
        print("-" * 80)
        print("TEST 1: Initial Question (Establishes Context)")
        print("-" * 80)
        question1 = {
            "type": "chat",
            "id": str(uuid.uuid4()),
            "content": "How many alerts are still open?"
        }

        print(f"👤 USER: {question1['content']}")
        await websocket.send(json.dumps(question1))

        # Collect response
        response1 = ""
        async for message in websocket:
            msg = json.loads(message)
            if msg.get('type') == 'stream_chunk':
                response1 += msg.get('content', '')
            elif msg.get('type') == 'stream_complete':
                break

        print(f"🤖 BOT: {response1}\n")

        # Wait a moment before second question
        await asyncio.sleep(1)

        # Test Case 2: Follow-up question (requires context)
        print("-" * 80)
        print("TEST 2: Follow-up Question (Requires Context from Test 1)")
        print("-" * 80)
        question2 = {
            "type": "chat",
            "id": str(uuid.uuid4()),
            "content": "Who are they assigned to?"
        }

        print(f"👤 USER: {question2['content']}")
        await websocket.send(json.dumps(question2))

        # Collect response
        response2 = ""
        async for message in websocket:
            msg = json.loads(message)
            if msg.get('type') == 'stream_chunk':
                response2 += msg.get('content', '')
            elif msg.get('type') == 'stream_complete':
                break

        print(f"🤖 BOT: {response2}\n")

        # Evaluate results
        print("=" * 80)
        print("TEST RESULTS")
        print("=" * 80)

        # Check if second response shows context understanding
        context_lost_phrases = [
            "lacks context",
            "need more information",
            "what you're referring to",
            "could you specify",
            "I don't understand"
        ]

        context_lost = any(phrase.lower() in response2.lower() for phrase in context_lost_phrases)

        if context_lost:
            print("❌ FAILED: Bot lost context - doesn't understand 'they' refers to open alerts")
            print("   Bot response contains phrases indicating missing context")
        else:
            print("✅ PASSED: Bot maintained context - understood 'they' = open alerts from previous question")

        print("\nExpected behavior:")
        print("  - First question: Bot queries database and returns count of open alerts")
        print("  - Second question: Bot understands 'they' refers to those alerts and shows assignments")
        print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        asyncio.run(test_context_aware_chat())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
