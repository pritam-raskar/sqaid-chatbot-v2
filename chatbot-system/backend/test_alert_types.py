import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8000/ws/chat"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Receive connection acknowledgment
        response = await websocket.recv()
        print(f"Connection response: {response}")
        
        # Send message
        message = "show me the count of alerts for each alert types"
        print(f"\nSending: {message}")

        await websocket.send(json.dumps({
            "content": message,
            "type": "chat"
        }))
        
        # Receive responses
        full_response = ""
        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                
                response_type = data.get("type")
                print(f"Response type: {response_type}")
                
                if response_type == "stream_chunk":
                    chunk = data.get("content", "")
                    print(f"Chunk: {chunk}")
                    full_response += chunk
                elif response_type == "stream_complete":
                    break
                elif response_type == "error":
                    print(f"Error: {data.get('message')}")
                    break
                    
            except websockets.exceptions.ConnectionClosed:
                break
        
        print(f"\n=== Complete Response ===")
        print(full_response)
        print("========================")

if __name__ == "__main__":
    asyncio.run(test_chat())
