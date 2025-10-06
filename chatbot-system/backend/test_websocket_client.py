"""
Simple WebSocket client to test LangGraph orchestration.
"""
import asyncio
import json
import websockets

async def test_langgraph_query():
    """Test LangGraph with a simple query."""
    uri = "ws://localhost:8000/ws/chat"
    
    print("🔌 Connecting to WebSocket...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Wait for connection confirmation
            response = await websocket.recv()
            print(f"📨 Server: {response}\n")
            
            # Send test query
            test_message = {
                "type": "chat",
                "content": "how many alerts are available?"
            }
            
            print(f"📤 Sending: {test_message['content']}")
            await websocket.send(json.dumps(test_message))
            
            # Receive all responses
            print("\n" + "="*60)
            print("WORKFLOW EXECUTION")
            print("="*60 + "\n")
            
            message_count = 0
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    message_count += 1
                    
                    data = json.loads(response)
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "node_update":
                        node = data.get("node", "unknown")
                        status = data.get("status", "unknown")
                        print(f"🔄 [{node}] {status}")
                        
                        if "message" in data:
                            print(f"   💬 {data['message']}")
                    
                    elif msg_type == "agent_response":
                        agent = data.get("agent", "unknown")
                        print(f"\n🤖 Agent: {agent}")
                        if "result" in data:
                            result = data["result"]
                            if isinstance(result, dict):
                                print(f"   📊 Result: {json.dumps(result, indent=2)}")
                            else:
                                print(f"   📊 Result: {result}")
                    
                    elif msg_type == "message":
                        content = data.get("content", "")
                        print(f"\n💬 Assistant: {content}")
                    
                    elif msg_type == "tool_call":
                        tool = data.get("tool_name", "unknown")
                        args = data.get("arguments", {})
                        print(f"\n🔧 Tool Call: {tool}")
                        print(f"   Args: {json.dumps(args, indent=2)}")
                    
                    elif msg_type == "tool_result":
                        tool = data.get("tool_name", "unknown")
                        result = data.get("result", "")
                        print(f"\n✅ Tool Result: {tool}")
                        if isinstance(result, dict) or isinstance(result, list):
                            print(f"   {json.dumps(result, indent=2)[:200]}...")
                        else:
                            print(f"   {str(result)[:200]}...")
                    
                    elif msg_type == "error":
                        error = data.get("error", "Unknown error")
                        print(f"\n❌ Error: {error}")
                        break
                    
                    elif msg_type == "done":
                        print(f"\n✅ Workflow complete!")
                        break

                    elif msg_type == "stream_chunk":
                        content = data.get("content", "")
                        print(content, end='', flush=True)

                    elif msg_type == "stream_complete":
                        print(f"\n\n✅ Response stream complete!")
                        break
                    
                    else:
                        print(f"\n📦 {msg_type}: {json.dumps(data, indent=2)[:200]}")
                
                except asyncio.TimeoutError:
                    print("\n⏱️ Timeout waiting for response")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed")
                    break
            
            print(f"\n{'='*60}")
            print(f"Total messages received: {message_count}")
            print(f"{'='*60}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Testing LangGraph Multi-Agent Orchestration")
    print("="*60 + "\n")
    asyncio.run(test_langgraph_query())
