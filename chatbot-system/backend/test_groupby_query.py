"""
Test LangGraph with GROUP BY query
"""
import asyncio
import json
import websockets

async def test_groupby_query():
    """Test LangGraph with a GROUP BY aggregation query."""
    uri = "ws://localhost:8000/ws/chat"
    
    print("🧪 Testing LangGraph with GROUP BY Query")
    print("="*60)
    print("Query: Give me number of alerts of each alert types\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for connection
            await websocket.recv()
            
            # Send test query
            test_message = {
                "type": "chat",
                "content": "Give me number of alerts of each alert types"
            }
            
            await websocket.send(json.dumps(test_message))
            
            print("RESPONSE:")
            print("="*60 + "\n")
            
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "stream_chunk":
                        content = data.get("content", "")
                        print(content, end='', flush=True)
                    
                    elif msg_type == "stream_complete":
                        print("\n\n" + "="*60)
                        print("✅ Query completed successfully!")
                        break
                    
                    elif msg_type == "error":
                        error = data.get("error", "Unknown error")
                        print(f"\n❌ Error: {error}")
                        break
                
                except asyncio.TimeoutError:
                    print("\n⏱️ Timeout - no response received")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed")
                    break
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_groupby_query())
