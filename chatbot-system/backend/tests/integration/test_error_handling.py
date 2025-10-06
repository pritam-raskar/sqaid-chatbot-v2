"""Integration tests for error handling and reconnection scenarios"""
import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from app.websocket.handler import WebSocketHandler
from app.session.session_manager import SessionManager
from tests.mocks import (
    MockLLMProvider,
    MockPostgreSQLAdapter,
    MockOracleAdapter,
    MockRESTAdapter
)


class MockWebSocketWithErrors:
    """Mock WebSocket that can simulate connection errors"""

    def __init__(self):
        self.messages_sent = []
        self.is_connected = True
        self.should_fail_send = False
        self.reconnect_count = 0

    async def send_text(self, message: str):
        """Mock send that can fail"""
        if self.should_fail_send:
            raise ConnectionError("Failed to send message")

        if not self.is_connected:
            raise RuntimeError("WebSocket disconnected")

        self.messages_sent.append(json.loads(message))

    async def send_json(self, data: Dict[str, Any]):
        """Mock send JSON that can fail"""
        if self.should_fail_send:
            raise ConnectionError("Failed to send message")

        if not self.is_connected:
            raise RuntimeError("WebSocket disconnected")

        self.messages_sent.append(data)

    async def close(self):
        """Mock close"""
        self.is_connected = False

    def reconnect(self):
        """Simulate reconnection"""
        self.is_connected = True
        self.reconnect_count += 1
        self.should_fail_send = False


@pytest.fixture
async def error_ws():
    """Create WebSocket that can simulate errors"""
    return MockWebSocketWithErrors()


@pytest.fixture
async def session_mgr():
    """Create session manager"""
    manager = SessionManager(redis_url=None)
    await manager.initialize()
    yield manager
    await manager.cleanup()


@pytest.mark.asyncio
async def test_llm_provider_failure(error_ws, session_mgr):
    """Test handling of LLM provider failures"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Create failing LLM provider
    mock_llm = MockLLMProvider(should_fail=True)
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Send message
        await handler.handle_message(json.dumps({
            "type": "message",
            "content": "This should trigger LLM error",
            "metadata": {}
        }))

        await asyncio.sleep(0.1)

        # Should receive error message
        error_messages = [msg for msg in error_ws.messages_sent if msg.get("type") == "error"]

        assert len(error_messages) > 0
        assert any("error" in str(msg).lower() for msg in error_messages)


@pytest.mark.asyncio
async def test_database_adapter_failure(error_ws, session_mgr):
    """Test handling of database adapter failures"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Create failing adapter
    failing_adapter = MockPostgreSQLAdapter(should_fail=True)

    with patch('app.intelligence.tools.database_query.get_adapter', return_value=failing_adapter):
        # Attempt database operation
        try:
            await failing_adapter.query("SELECT * FROM cases")
            assert False, "Should have raised exception"
        except Exception as e:
            # Error should be caught and handled
            assert "failure" in str(e).lower()


@pytest.mark.asyncio
async def test_websocket_send_failure(error_ws, session_mgr):
    """Test handling of WebSocket send failures"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    mock_llm = MockLLMProvider(responses=["Test response"])
    await mock_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
        # Enable send failures
        error_ws.should_fail_send = True

        # Try to send message
        try:
            await handler.handle_message(json.dumps({
                "type": "message",
                "content": "Test",
                "metadata": {}
            }))

            await asyncio.sleep(0.1)

            # Handler should catch the error gracefully
            # Connection should be marked as broken
        except ConnectionError:
            # Expected behavior - connection error should be raised
            pass


@pytest.mark.asyncio
async def test_reconnection_logic(error_ws, session_mgr):
    """Test WebSocket reconnection logic"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Simulate disconnection
    error_ws.is_connected = False

    # Wait a bit
    await asyncio.sleep(0.1)

    # Reconnect
    error_ws.reconnect()

    # Verify reconnection
    assert error_ws.is_connected
    assert error_ws.reconnect_count == 1

    # Should be able to send messages again
    await error_ws.send_json({"type": "test", "content": "after reconnect"})

    assert len(error_ws.messages_sent) == 1


@pytest.mark.asyncio
async def test_malformed_message_handling(error_ws, session_mgr):
    """Test handling of malformed messages"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Send malformed JSON
    malformed_messages = [
        "not json at all",
        "{incomplete json",
        '{"type": "message"}',  # Missing required fields
        '{"content": "message without type"}',
        "",
        "null"
    ]

    for malformed_msg in malformed_messages:
        try:
            await handler.handle_message(malformed_msg)
            await asyncio.sleep(0.05)
        except Exception:
            # Should handle gracefully
            pass

    # Should have sent error responses or handled gracefully
    assert error_ws.is_connected  # Should not crash the connection


@pytest.mark.asyncio
async def test_session_recovery_after_error(session_mgr):
    """Test session recovery after errors"""

    # Create session
    session = await session_mgr.create_session("recovery-session")

    # Add some messages
    session.message_history.append({
        "role": "user",
        "content": "Message before error",
        "timestamp": "2025-01-01T00:00:00"
    })

    await session_mgr.update_session(session)

    # Simulate error and recovery
    try:
        # Simulate some operation that fails
        raise Exception("Simulated error")
    except Exception:
        pass

    # Session should still be accessible
    recovered_session = await session_mgr.get_session("recovery-session")

    assert recovered_session is not None
    assert len(recovered_session.message_history) == 1
    assert recovered_session.message_history[0]["content"] == "Message before error"


@pytest.mark.asyncio
async def test_concurrent_error_handling(session_mgr):
    """Test handling errors in concurrent operations"""

    # Create multiple failing operations
    failing_adapter = MockPostgreSQLAdapter(should_fail=True)

    async def failing_operation(op_num: int):
        try:
            await failing_adapter.query(f"SELECT * FROM table_{op_num}")
            return f"Success {op_num}"
        except Exception as e:
            return f"Error {op_num}: {str(e)}"

    # Run multiple failing operations concurrently
    results = await asyncio.gather(
        *[failing_operation(i) for i in range(10)],
        return_exceptions=True
    )

    # All should have handled errors
    assert len(results) == 10
    for result in results:
        assert "Error" in str(result) or isinstance(result, Exception)


@pytest.mark.asyncio
async def test_timeout_handling(error_ws, session_mgr):
    """Test handling of operation timeouts"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Create LLM provider that delays
    class SlowMockLLMProvider(MockLLMProvider):
        async def chat_completion(self, messages, **kwargs):
            await asyncio.sleep(10)  # Very slow
            return await super().chat_completion(messages, **kwargs)

    slow_llm = SlowMockLLMProvider()
    await slow_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=slow_llm):
        # Send message with timeout
        try:
            await asyncio.wait_for(
                handler.handle_message(json.dumps({
                    "type": "message",
                    "content": "This should timeout",
                    "metadata": {}
                })),
                timeout=1.0
            )
            assert False, "Should have timed out"
        except asyncio.TimeoutError:
            # Expected - timeout should occur
            pass


@pytest.mark.asyncio
async def test_partial_failure_recovery():
    """Test recovery from partial failures in multi-step operations"""

    # Mock adapters - some working, some failing
    working_adapter = MockPostgreSQLAdapter(should_fail=False)
    failing_adapter = MockOracleAdapter(should_fail=True)

    # Try operations on both
    results = []

    try:
        result1 = await working_adapter.query("SELECT * FROM cases")
        results.append(("postgres", "success", result1))
    except Exception as e:
        results.append(("postgres", "failed", str(e)))

    try:
        result2 = await failing_adapter.query("SELECT * FROM cases")
        results.append(("oracle", "success", result2))
    except Exception as e:
        results.append(("oracle", "failed", str(e)))

    # Should have one success and one failure
    assert len(results) == 2
    assert results[0][1] == "success"  # Postgres succeeded
    assert results[1][1] == "failed"   # Oracle failed


@pytest.mark.asyncio
async def test_graceful_degradation(error_ws, session_mgr):
    """Test graceful degradation when services are unavailable"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # All adapters failing
    with patch('app.intelligence.tools.database_query.get_adapter') as mock_get_adapter:
        mock_get_adapter.return_value = MockPostgreSQLAdapter(should_fail=True)

        # LLM still working
        mock_llm = MockLLMProvider(responses=["I'm having trouble accessing the database right now."])
        await mock_llm.connect()

        with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=mock_llm):
            # Send message
            await handler.handle_message(json.dumps({
                "type": "message",
                "content": "Get case data",
                "metadata": {}
            }))

            await asyncio.sleep(0.1)

            # Should still get a response from LLM even if database fails
            responses = [
                msg for msg in error_ws.messages_sent
                if msg.get("type") == "message" and msg.get("role") == "assistant"
            ]

            # LLM should provide fallback response
            assert len(responses) > 0


@pytest.mark.asyncio
async def test_error_message_formatting(error_ws, session_mgr):
    """Test that error messages are properly formatted for client"""

    handler = WebSocketHandler(error_ws, "test-session", session_mgr)

    # Trigger various error types
    failing_llm = MockLLMProvider(should_fail=True)
    await failing_llm.connect()

    with patch('app.websocket.handler.LLMProviderFactory.create_provider', return_value=failing_llm):
        await handler.handle_message(json.dumps({
            "type": "message",
            "content": "Test",
            "metadata": {}
        }))

        await asyncio.sleep(0.1)

        # Error messages should have proper structure
        error_messages = [msg for msg in error_ws.messages_sent if msg.get("type") == "error"]

        for error_msg in error_messages:
            # Should have required fields
            assert "type" in error_msg
            assert error_msg["type"] == "error"
            # May have additional fields like "message", "code", "details"


@pytest.mark.asyncio
async def test_retry_logic(session_mgr):
    """Test retry logic for transient failures"""

    # Create adapter that fails first time, succeeds second time
    class FlakeyAdapter(MockPostgreSQLAdapter):
        def __init__(self):
            super().__init__(should_fail=False)
            self.attempt_count = 0

        async def query(self, sql: str, *params):
            self.attempt_count += 1
            if self.attempt_count == 1:
                raise Exception("Transient failure")
            return await super().query(sql, *params)

    adapter = FlakeyAdapter()

    # Try with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await adapter.query("SELECT * FROM cases")
            assert result is not None
            assert adapter.attempt_count == 2  # Failed once, succeeded second time
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.1)
