"""
Test GROUP BY with explicit column name
"""
import asyncio
import json
import websockets

async def test():
    uri = "ws://localhost:8000/ws/chat"
    
    print("🧪 Testing GROUP BY Query")
    print("="*60 + "\n")
    
    async with websockets.connect(uri) as ws:
        await ws.recv()  # Connection message
        
        await ws.send(json.dumps({
            "type": "chat",
            "content": "Give me number of alerts for each alert_type_id. Show alert_type_id and count."
        }))
        
        print("RESPONSE:\n" + "="*60 + "\n")
        
        while True:
            try:
                data = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if data.get("type") == "stream_chunk":
                    print(data.get("content", ""), end='', flush=True)
                elif data.get("type") == "stream_complete":
                    print("\n\n" + "="*60)
                    break
                elif data.get("type") == "error":
                    print(f"\n❌ {data.get('error')}")
                    break
            except asyncio.TimeoutError:
                break

if __name__ == "__main__":
    asyncio.run(test())
