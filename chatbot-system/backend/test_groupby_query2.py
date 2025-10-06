"""
Test LangGraph with GROUP BY query - attempt 2
"""
import asyncio
import json
import websockets

async def test_groupby_query():
    """Test LangGraph with a GROUP BY aggregation query."""
    uri = "ws://localhost:8000/ws/chat"
    
    print("🧪 Testing LangGraph with GROUP BY Query (Attempt 2)")
    print("="*60)
    print("Query: Count alerts grouped by alert_type_id from cm_alerts table\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            # Wait for connection
            await websocket.recv()
            
            # Send test query - more explicit about column name
            test_message = {
                "type": "chat",
                "content": "Count alerts grouped by alert_type_id from cm_alerts table. Show me alert_type_id and count for each."
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
