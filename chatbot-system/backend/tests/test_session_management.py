"""
Session Management Integration Tests
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import json
from datetime import datetime, timedelta

from app.orchestration.session_manager import SessionManager
from tests.mocks import MockSessionData


class TestSessionManagement:
    """Test session management with Redis and fallback"""

    @pytest.mark.asyncio
    async def test_create_new_session(self, mock_session_manager):
        """Test creating a new session"""
        session_id = await mock_session_manager.create_session()

        assert session_id is not None
        assert len(session_id) > 0
        assert session_id.startswith("sess-")

    @pytest.mark.asyncio
    async def test_get_existing_session(self, mock_session_manager):
        """Test retrieving an existing session"""
        # Create session
        session_id = await mock_session_manager.create_session()

        # Store some data
        session_data = MockSessionData.get_session_with_history()
        await mock_session_manager.update_session(session_id, session_data)

        # Retrieve session
        retrieved = await mock_session_manager.get_session(session_id)
        assert retrieved is not None
        assert retrieved["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_update_session_history(self, mock_session_manager):
        """Test updating conversation history"""
        session_id = await mock_session_manager.create_session()

        # Add messages to history
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        await mock_session_manager.add_messages(session_id, messages)

        session = await mock_session_manager.get_session(session_id)
        assert "conversation_history" in session
        assert len(session["conversation_history"]) >= 2

    @pytest.mark.asyncio
    async def test_session_expiration(self, mock_session_manager):
        """Test session expiration handling"""
        session_id = await mock_session_manager.create_session()

        # Set TTL
        await mock_session_manager.set_session_ttl(session_id, ttl_seconds=1)

        # Wait for expiration
        await asyncio.sleep(2)

        # Session should be expired
        session = await mock_session_manager.get_session(session_id)
        assert session is None or session.get("expired", False)

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_session_manager):
        """Test deleting a session"""
        session_id = await mock_session_manager.create_session()

        # Delete session
        result = await mock_session_manager.delete_session(session_id)
        assert result is True

        # Verify deletion
        session = await mock_session_manager.get_session(session_id)
        assert session is None

    @pytest.mark.asyncio
    async def test_redis_fallback_to_memory(self):
        """Test fallback to in-memory storage when Redis unavailable"""
        # Create manager with invalid Redis URL
        manager = SessionManager(redis_url="redis://invalid:9999")
        await manager.initialize()

        # Should fallback to memory storage
        session_id = await manager.create_session()
        assert session_id is not None

        # Should still work with memory storage
        session_data = {"test": "data"}
        await manager.update_session(session_id, session_data)

        retrieved = await manager.get_session(session_id)
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_concurrent_session_updates(self, mock_session_manager):
        """Test concurrent updates to same session"""
        session_id = await mock_session_manager.create_session()

        # Simulate concurrent updates
        async def update_session(msg_id: int):
            await mock_session_manager.add_messages(
                session_id,
                [{"role": "user", "content": f"Message {msg_id}"}]
            )

        # Run multiple updates concurrently
        await asyncio.gather(*[update_session(i) for i in range(5)])

        # Verify all messages were added
        session = await mock_session_manager.get_session(session_id)
        assert len(session["conversation_history"]) >= 5

    @pytest.mark.asyncio
    async def test_session_context_persistence(self, mock_session_manager):
        """Test persistence of user context across requests"""
        session_id = await mock_session_manager.create_session()

        # Set user context
        user_context = {
            "user_id": "user-123",
            "role": "agent",
            "current_case": "12345"
        }
        await mock_session_manager.set_context(session_id, user_context)

        # Retrieve and verify
        session = await mock_session_manager.get_session(session_id)
        assert session["user_context"] == user_context

        # Update context
        await mock_session_manager.update_context(
            session_id,
            {"current_case": "67890"}
        )

        session = await mock_session_manager.get_session(session_id)
        assert session["user_context"]["current_case"] == "67890"

    @pytest.mark.asyncio
    async def test_session_message_limit(self, mock_session_manager):
        """Test session history message limit"""
        session_id = await mock_session_manager.create_session()

        # Add many messages
        for i in range(150):
            await mock_session_manager.add_messages(
                session_id,
                [{"role": "user", "content": f"Message {i}"}]
            )

        # Should maintain only last N messages (e.g., 100)
        session = await mock_session_manager.get_session(session_id)
        history_length = len(session["conversation_history"])
        assert history_length <= 100  # Assuming 100 message limit

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolation(self, mock_session_manager):
        """Test isolation between multiple sessions"""
        # Create multiple sessions
        session1_id = await mock_session_manager.create_session()
        session2_id = await mock_session_manager.create_session()

        # Add different data to each
        await mock_session_manager.add_messages(
            session1_id,
            [{"role": "user", "content": "Session 1 message"}]
        )
        await mock_session_manager.add_messages(
            session2_id,
            [{"role": "user", "content": "Session 2 message"}]
        )

        # Verify isolation
        session1 = await mock_session_manager.get_session(session1_id)
        session2 = await mock_session_manager.get_session(session2_id)

        assert session1["conversation_history"][0]["content"] == "Session 1 message"
        assert session2["conversation_history"][0]["content"] == "Session 2 message"
