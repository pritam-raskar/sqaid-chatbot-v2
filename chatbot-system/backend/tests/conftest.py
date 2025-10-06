"""
Pytest configuration and fixtures for integration tests
"""
import pytest
import asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import json
from httpx import AsyncClient
from fastapi.testclient import TestClient
from websocket import create_connection
import redis
from asyncpg import create_pool

from app.main import app
from app.core.config import ConfigLoader
from app.orchestration.session_manager import SessionManager
from app.orchestration.websocket_handler import WebSocketHandler
from app.llm.providers.eliza_provider import ElizaProvider


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_config():
    """Load test configuration"""
    config = ConfigLoader()
    config.config = {
        "app": {
            "name": "chatbot-test",
            "version": "1.0.0",
            "environment": "test",
            "debug": True
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8001,
            "reload": False
        },
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 1,
            "decode_responses": True
        },
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "test_chatbot_db",
            "user": "test_user",
            "password": "test_password"
        },
        "llm": {
            "provider": "eliza",
            "eliza": {
                "base_url": "http://mock-eliza.test",
                "cert_path": "/path/to/cert.pem",
                "key_path": "/path/to/key.pem",
                "max_retries": 3,
                "timeout": 30
            }
        },
        "websocket": {
            "heartbeat_interval": 30,
            "message_queue_size": 100,
            "reconnect_attempts": 3
        }
    }
    return config


@pytest.fixture
async def mock_redis():
    """Mock Redis client"""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=False)
    redis_mock.expire = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
async def mock_session_manager(mock_redis):
    """Mock session manager with Redis"""
    with patch('app.orchestration.session_manager.redis.from_url', return_value=mock_redis):
        manager = SessionManager(redis_url="redis://localhost:6379/1")
        await manager.initialize()
        return manager


@pytest.fixture
async def mock_eliza_provider():
    """Mock Eliza LLM provider"""
    provider = AsyncMock(spec=ElizaProvider)
    provider.connect = AsyncMock(return_value=True)
    provider.disconnect = AsyncMock(return_value=True)
    provider.chat_completion = AsyncMock(return_value={
        "response": "This is a mock response from Eliza",
        "message_id": "mock-msg-123",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    })
    provider.stream_completion = AsyncMock()

    async def mock_stream():
        chunks = ["This ", "is ", "a ", "streamed ", "response"]
        for chunk in chunks:
            yield {"content": chunk, "done": False}
        yield {"content": "", "done": True}

    provider.stream_completion.return_value = mock_stream()
    return provider


@pytest.fixture
async def mock_websocket_handler(mock_session_manager, mock_eliza_provider):
    """Mock WebSocket handler"""
    with patch('app.orchestration.websocket_handler.ElizaProvider', return_value=mock_eliza_provider):
        handler = WebSocketHandler(mock_session_manager)
        return handler


@pytest.fixture
async def test_client():
    """Create test client for FastAPI app"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_test_client():
    """Create synchronous test client for WebSocket testing"""
    return TestClient(app)


@pytest.fixture
async def mock_postgres_pool():
    """Mock PostgreSQL connection pool"""
    pool = MagicMock()

    # Mock connection
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"id": 1, "name": "Test Case", "status": "open"},
        {"id": 2, "name": "Another Case", "status": "closed"}
    ])
    conn.fetchrow = AsyncMock(return_value={"id": 1, "name": "Test Case"})
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    # Mock transaction
    transaction = AsyncMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)

    # Pool acquire
    acquire_context = AsyncMock()
    acquire_context.__aenter__ = AsyncMock(return_value=conn)
    acquire_context.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_context)

    return pool


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing"""
    return [
        {
            "type": "chat",
            "content": "What is the status of case #12345?",
            "message_id": "msg-001",
            "timestamp": "2024-01-15T10:00:00Z"
        },
        {
            "type": "chat",
            "content": "Show me all open cases",
            "message_id": "msg-002",
            "timestamp": "2024-01-15T10:01:00Z"
        },
        {
            "type": "action",
            "action": "filter_cases",
            "data": {"status": "open"},
            "message_id": "msg-003",
            "timestamp": "2024-01-15T10:02:00Z"
        }
    ]


@pytest.fixture
def mock_api_responses():
    """Mock responses for REST API adapter testing"""
    return {
        "/api/cases": {
            "cases": [
                {"id": "12345", "title": "Account Issue", "status": "open"},
                {"id": "67890", "title": "Payment Problem", "status": "resolved"}
            ],
            "total": 2
        },
        "/api/cases/12345": {
            "id": "12345",
            "title": "Account Issue",
            "status": "open",
            "description": "Customer unable to access account",
            "priority": "high",
            "assigned_to": "agent-001"
        },
        "/api/user/profile": {
            "id": "user-123",
            "name": "Test User",
            "email": "test@example.com",
            "role": "customer"
        }
    }


@pytest.fixture
async def cleanup_redis():
    """Cleanup Redis after tests"""
    yield
    try:
        r = redis.Redis(host='localhost', port=6379, db=1)
        r.flushdb()
    except:
        pass  # Redis might not be available in test environment


@pytest.fixture
async def cleanup_postgres():
    """Cleanup PostgreSQL after tests"""
    yield
    # Cleanup would go here if using real database
    pass