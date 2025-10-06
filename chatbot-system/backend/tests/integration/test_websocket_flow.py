"""Integration tests for complete WebSocket message flow"""
import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.websocket.handler import WebSocketHandler
from app.session.session_manager import SessionManager
from tests.mocks import MockLLMProvider, MockPostgreSQLAdapter


class MockWebSocket:
    """Mock WebSocket connection for testing"""

    def __init__(self):
        self.messages_sent = []
        self.is_open = True

    async def send_text(self, message: str):
        """Mock send text"""
        self.messages_sent.append(json.loads(message))

    async def send_json(self, data: Dict[str, Any]):
        """Mock send JSON"""
        self.messages_sent.append(data)

    async def close(self):
        """Mock close"""
        self.is_open = False


@pytest.fixture
async def mock_websocket():
    """Create mock WebSocket"""
    return MockWebSocket()


@pytest.fixture
async def session_manager():
    """Create session manager with in-memory storage"""
    manager = SessionManager(redis_url=None)
    await manager.initialize()
    yield manager
    await manager.cleanup()


@pytest.fixture
async def ws_handler(session_manager, mock_websocket):
    """Create WebSocket handler with mocks"""
    handler = WebSocketHandler(
        websocket=mock_websocket,
        session_id="test-session-123",
        session_manager=session_manager
    )
    return handler


@pytest.mark.asyncio
async def test_complete_message_flow(ws_handler, mock_websocket):
    """Test complete message flow from user input to LLM response"""

    # Mock the LLM provider
    mock_llm = MockLLMProvider(responses=["Hello! How can I help you today?"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send user message
        user_message = {
            "type": "message",
            "content": "Hello, I need help with a case",
            "metadata": {}
        }

        await ws_handler.handle_message(json.dumps(user_message))

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check that messages were sent
        assert len(mock_websocket.messages_sent) > 0

        # Find the assistant response
        responses = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("type") == "message" and msg.get("role") == "assistant"
        ]

        assert len(responses) > 0
        assert "Hello! How can I help you today?" in responses[0]["content"]


@pytest.mark.asyncio
async def test_streaming_message_flow(ws_handler, mock_websocket):
    """Test streaming message flow"""

    mock_llm = MockLLMProvider(responses=["This is a streaming response"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send user message with streaming enabled
        user_message = {
            "type": "message",
            "content": "Tell me about streaming",
            "metadata": {"stream": True}
        }

        await ws_handler.handle_message(json.dumps(user_message))

        # Wait for streaming to complete
        await asyncio.sleep(0.2)

        # Check that stream chunks were sent
        stream_chunks = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("type") == "stream_chunk"
        ]

        assert len(stream_chunks) > 0

        # Check that stream ended
        stream_end = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("type") == "stream_end"
        ]

        assert len(stream_end) == 1


@pytest.mark.asyncio
async def test_error_handling_in_flow(ws_handler, mock_websocket):
    """Test error handling in message flow"""

    # Create failing LLM provider
    mock_llm = MockLLMProvider(should_fail=True)
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send user message
        user_message = {
            "type": "message",
            "content": "This should fail",
            "metadata": {}
        }

        await ws_handler.handle_message(json.dumps(user_message))

        # Wait for error processing
        await asyncio.sleep(0.1)

        # Check that error was sent
        error_messages = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("type") == "error"
        ]

        assert len(error_messages) > 0
        assert "error" in error_messages[0].get("content", "").lower()


@pytest.mark.asyncio
async def test_session_context_in_flow(ws_handler, session_manager):
    """Test that session context is maintained across messages"""

    mock_llm = MockLLMProvider(responses=["Response 1", "Response 2"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send first message
        await ws_handler.handle_message(json.dumps({
            "type": "message",
            "content": "First message",
            "metadata": {}
        }))

        await asyncio.sleep(0.1)

        # Send second message
        await ws_handler.handle_message(json.dumps({
            "type": "message",
            "content": "Second message",
            "metadata": {}
        }))

        await asyncio.sleep(0.1)

        # Retrieve session
        session = await session_manager.get_session("test-session-123")

        # Check that both messages are in history
        assert len(session.message_history) >= 2
        assert any("First message" in msg.get("content", "") for msg in session.message_history)
        assert any("Second message" in msg.get("content", "") for msg in session.message_history)


@pytest.mark.asyncio
async def test_metadata_propagation(ws_handler, mock_websocket):
    """Test that metadata is properly propagated through the flow"""

    mock_llm = MockLLMProvider(responses=["Response with metadata"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send message with metadata
        user_message = {
            "type": "message",
            "content": "Message with metadata",
            "metadata": {
                "case_id": "12345",
                "priority": "high",
                "custom_field": "custom_value"
            }
        }

        await ws_handler.handle_message(json.dumps(user_message))

        await asyncio.sleep(0.1)

        # Check that metadata was preserved in responses
        messages_with_metadata = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("metadata") and msg["metadata"].get("case_id") == "12345"
        ]

        assert len(messages_with_metadata) > 0


@pytest.mark.asyncio
async def test_concurrent_sessions(session_manager):
    """Test handling multiple concurrent sessions"""

    # Create multiple handlers
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    handler1 = WebSocketHandler(ws1, "session-1", session_manager)
    handler2 = WebSocketHandler(ws2, "session-2", session_manager)

    mock_llm = MockLLMProvider(responses=["Response 1", "Response 2"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send messages to both handlers concurrently
        await asyncio.gather(
            handler1.handle_message(json.dumps({
                "type": "message",
                "content": "Message to session 1",
                "metadata": {}
            })),
            handler2.handle_message(json.dumps({
                "type": "message",
                "content": "Message to session 2",
                "metadata": {}
            }))
        )

        await asyncio.sleep(0.2)

        # Verify both sessions have their own messages
        session1 = await session_manager.get_session("session-1")
        session2 = await session_manager.get_session("session-2")

        assert session1 is not None
        assert session2 is not None
        assert session1.session_id != session2.session_id


@pytest.mark.asyncio
async def test_message_ordering(ws_handler, mock_websocket):
    """Test that messages maintain proper ordering"""

    mock_llm = MockLLMProvider(responses=["Response"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send multiple messages rapidly
        messages = [
            {"type": "message", "content": f"Message {i}", "metadata": {}}
            for i in range(5)
        ]

        for msg in messages:
            await ws_handler.handle_message(json.dumps(msg))

        await asyncio.sleep(0.3)

        # Check message order in sent messages
        user_messages = [
            msg for msg in mock_websocket.messages_sent
            if msg.get("role") == "user"
        ]

        # Verify messages appear in order
        for i in range(len(user_messages) - 1):
            current_content = user_messages[i].get("content", "")
            next_content = user_messages[i + 1].get("content", "")

            if "Message" in current_content and "Message" in next_content:
                current_num = int(current_content.split()[-1])
                next_num = int(next_content.split()[-1])
                assert next_num > current_num
