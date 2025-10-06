"""
End-to-End Integration Tests for Chatbot System
"""
import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock, MagicMock
from websocket import create_connection
import websocket

from app.main import app
from fastapi.testclient import TestClient


class TestEndToEndFlow:
    """Test complete message flow through the system"""

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, sync_test_client, mock_session_manager):
        """Test WebSocket connection establishment and lifecycle"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            # Test connection message
            data = ws.receive_json()
            assert data["type"] == "connection"
            assert data["status"] == "connected"
            assert "session_id" in data

            # Send a ping to test heartbeat
            ws.send_json({"type": "ping"})
            response = ws.receive_json()
            assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_chat_message_flow(self, sync_test_client, mock_eliza_provider):
        """Test sending and receiving chat messages"""
        with patch('app.orchestration.websocket_handler.ElizaProvider', return_value=mock_eliza_provider):
            with sync_test_client.websocket_connect("/ws/chat") as ws:
                # Get connection confirmation
                connection_msg = ws.receive_json()
                session_id = connection_msg["session_id"]

                # Send chat message
                chat_message = {
                    "type": "chat",
                    "content": "What is the status of case #12345?",
                    "message_id": "test-msg-001"
                }
                ws.send_json(chat_message)

                # Receive response
                response = ws.receive_json()
                assert response["type"] == "message"
                assert "content" in response
                assert response["role"] == "assistant"
                assert response["message_id"] == "test-msg-001"

    @pytest.mark.asyncio
    async def test_streaming_response(self, sync_test_client, mock_eliza_provider):
        """Test streaming response from LLM"""
        with patch('app.orchestration.websocket_handler.ElizaProvider', return_value=mock_eliza_provider):
            with sync_test_client.websocket_connect("/ws/chat") as ws:
                # Get connection confirmation
                ws.receive_json()

                # Send message requesting stream
                chat_message = {
                    "type": "chat",
                    "content": "Explain the case in detail",
                    "message_id": "test-msg-002",
                    "stream": True
                }
                ws.send_json(chat_message)

                # Collect streamed chunks
                chunks = []
                while True:
                    response = ws.receive_json()
                    if response["type"] == "stream_chunk":
                        chunks.append(response["content"])
                        if response.get("done", False):
                            break

                # Verify we received multiple chunks
                assert len(chunks) > 1
                full_response = "".join(chunks[:-1])  # Last chunk is empty with done=True
                assert len(full_response) > 0

    @pytest.mark.asyncio
    async def test_error_handling(self, sync_test_client):
        """Test error handling for invalid messages"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            # Get connection confirmation
            ws.receive_json()

            # Send invalid message
            invalid_message = {
                "type": "invalid_type",
                "data": "some data"
            }
            ws.send_json(invalid_message)

            # Should receive error response
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "message" in response

    @pytest.mark.asyncio
    async def test_session_persistence(self, sync_test_client, mock_session_manager):
        """Test session persistence across connections"""
        # First connection
        with sync_test_client.websocket_connect("/ws/chat") as ws1:
            conn_msg = ws1.receive_json()
            session_id = conn_msg["session_id"]

            # Send a message to establish history
            ws1.send_json({
                "type": "chat",
                "content": "Remember this: Project Alpha",
                "message_id": "msg-001"
            })
            ws1.receive_json()

        # Second connection with same session
        with sync_test_client.websocket_connect(f"/ws/chat?session_id={session_id}") as ws2:
            conn_msg = ws2.receive_json()
            assert conn_msg["session_id"] == session_id

            # Send message referencing previous context
            ws2.send_json({
                "type": "chat",
                "content": "What project did I mention?",
                "message_id": "msg-002"
            })
            response = ws2.receive_json()
            # In real scenario, LLM would reference Project Alpha
            assert response["type"] == "message"

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, sync_test_client):
        """Test multiple concurrent WebSocket connections"""
        connections = []
        session_ids = []

        try:
            # Create multiple connections
            for i in range(3):
                ws = sync_test_client.websocket_connect("/ws/chat").__enter__()
                connections.append(ws)
                conn_msg = ws.receive_json()
                session_ids.append(conn_msg["session_id"])

            # Verify all sessions are unique
            assert len(set(session_ids)) == 3

            # Send messages from each connection
            for i, ws in enumerate(connections):
                ws.send_json({
                    "type": "chat",
                    "content": f"Message from connection {i}",
                    "message_id": f"msg-{i}"
                })

            # Receive responses
            for ws in connections:
                response = ws.receive_json()
                assert response["type"] == "message"

        finally:
            # Cleanup connections
            for ws in connections:
                ws.__exit__(None, None, None)

    @pytest.mark.asyncio
    async def test_reconnection_with_session(self, sync_test_client, mock_session_manager):
        """Test reconnection with existing session ID"""
        # Initial connection
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            conn_msg = ws.receive_json()
            original_session_id = conn_msg["session_id"]

            # Send some messages
            ws.send_json({
                "type": "chat",
                "content": "Initial message",
                "message_id": "msg-001"
            })
            ws.receive_json()

        # Simulate reconnection with same session
        with sync_test_client.websocket_connect(f"/ws/chat?session_id={original_session_id}") as ws:
            conn_msg = ws.receive_json()
            assert conn_msg["session_id"] == original_session_id
            assert conn_msg["status"] == "connected"

    @pytest.mark.asyncio
    async def test_data_adapter_integration(self, sync_test_client, mock_postgres_pool):
        """Test integration with data adapters"""
        with patch('app.data.postgres_adapter.create_pool', return_value=mock_postgres_pool):
            with sync_test_client.websocket_connect("/ws/chat") as ws:
                ws.receive_json()  # Connection message

                # Send query that triggers database lookup
                ws.send_json({
                    "type": "chat",
                    "content": "Show me all cases from the database",
                    "message_id": "msg-db-001"
                })

                response = ws.receive_json()
                assert response["type"] == "message"
                # Response would contain database results in real scenario

    @pytest.mark.asyncio
    async def test_action_message_handling(self, sync_test_client):
        """Test handling of action messages for parent-child communication"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            ws.receive_json()  # Connection message

            # Send action message
            action_message = {
                "type": "action",
                "action": "update_filters",
                "data": {
                    "status": "open",
                    "priority": "high"
                },
                "message_id": "action-001"
            }
            ws.send_json(action_message)

            # Should receive acknowledgment
            response = ws.receive_json()
            assert response["type"] == "action_response"
            assert response["action"] == "update_filters"
            assert response["status"] == "success"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, sync_test_client):
        """Test rate limiting for message sending"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            ws.receive_json()  # Connection message

            # Send multiple messages rapidly
            for i in range(10):
                ws.send_json({
                    "type": "chat",
                    "content": f"Rapid message {i}",
                    "message_id": f"rapid-{i}"
                })

            # Should still receive responses (rate limiting would be configured)
            responses_received = 0
            for _ in range(10):
                try:
                    response = ws.receive_json(timeout=1)
                    if response["type"] == "message":
                        responses_received += 1
                except:
                    break

            assert responses_received > 0

    @pytest.mark.asyncio
    async def test_message_validation(self, sync_test_client):
        """Test message validation and error responses"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            ws.receive_json()  # Connection message

            # Test missing required fields
            invalid_messages = [
                {},  # Empty message
                {"type": "chat"},  # Missing content
                {"content": "test"},  # Missing type
                {"type": "chat", "content": "x" * 10001},  # Too long
            ]

            for msg in invalid_messages:
                ws.send_json(msg)
                response = ws.receive_json()
                assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, sync_test_client):
        """Test graceful shutdown of connections"""
        with sync_test_client.websocket_connect("/ws/chat") as ws:
            ws.receive_json()  # Connection message

            # Send close message
            ws.send_json({
                "type": "close",
                "reason": "user_initiated"
            })

            # Should receive close confirmation
            response = ws.receive_json()
            assert response["type"] == "close"
            assert response["status"] == "connection_closed"