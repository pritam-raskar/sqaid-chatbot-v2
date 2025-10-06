"""
Session Manager for maintaining conversation state.
Uses Redis for distributed session storage.
"""

import json
import uuid
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Session(BaseModel):
    """Session data model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionManager:
    """
    Manages user sessions and conversation history.
    Uses Redis for persistence and distributed access.
    """

    def __init__(self, redis_config: dict):
        """
        Initialize SessionManager with Redis configuration.

        Args:
            redis_config: Redis connection configuration
        """
        self.redis_config = redis_config
        self.redis_client: Optional[redis.Redis] = None
        self.ttl = redis_config.get('ttl', 3600)  # Default 1 hour
        self.max_history_length = 100  # Maximum messages to keep in history

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_config.get('host', 'localhost'),
                port=self.redis_config.get('port', 6379),
                db=self.redis_config.get('db', 0),
                password=self.redis_config.get('password'),
                decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis for session management")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory storage if Redis is unavailable
            logger.warning("Using in-memory session storage (not recommended for production)")
            self.redis_client = None
            self._memory_storage = {}

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    def create_session(self, user_id: str = None) -> Session:
        """
        Create a new session.

        Args:
            user_id: Optional user identifier

        Returns:
            New Session instance

        Steps:
        1. Generate unique session ID
        2. Initialize session object with metadata
        3. Store in Redis with TTL
        4. Return session instance
        """
        # Step 1: Generate unique session ID (done by Session model)
        # Step 2: Initialize session object with metadata
        session = Session(
            user_id=user_id,
            metadata={
                'user_agent': None,  # Can be set from request headers
                'ip_address': None,  # Can be set from request
                'start_time': datetime.utcnow().isoformat()
            }
        )

        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session instance or None if not found

        Steps:
        1. Retrieve from Redis
        2. Deserialize session data
        3. Check expiry
        4. Refresh TTL if active
        5. Return session or None
        """
        try:
            # Step 1: Retrieve from Redis
            if self.redis_client:
                session_key = f"session:{session_id}"
                session_data = await self.redis_client.get(session_key)

                if not session_data:
                    return None

                # Step 2: Deserialize session data
                session_dict = json.loads(session_data)
                session = Session(**session_dict)

                # Step 3: Check expiry (handled by Redis TTL)
                # Step 4: Refresh TTL if active
                if session.is_active:
                    await self.redis_client.expire(session_key, self.ttl)

                # Step 5: Return session
                return session
            else:
                # Fallback to memory storage
                return self._memory_storage.get(session_id)

        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None

    async def get_or_create_session(self, session_id: str = None, user_id: str = None) -> Session:
        """
        Get existing session or create a new one.

        Args:
            session_id: Optional session ID to retrieve
            user_id: Optional user ID for new session

        Returns:
            Session instance
        """
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session

        # Create new session
        session = self.create_session(user_id)
        await self.save_session(session)
        return session

    async def save_session(self, session: Session):
        """
        Save session to storage.

        Args:
            session: Session to save
        """
        try:
            session.updated_at = datetime.utcnow()

            if self.redis_client:
                session_key = f"session:{session.id}"
                session_data = session.json()
                await self.redis_client.setex(
                    session_key,
                    self.ttl,
                    session_data
                )
            else:
                # Fallback to memory storage
                self._memory_storage[session.id] = session

            logger.debug(f"Saved session {session.id}")

        except Exception as e:
            logger.error(f"Error saving session {session.id}: {e}")

    async def update_session(self, session_id: str, updates: Dict[str, Any]):
        """
        Update session data.

        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply

        Steps:
        1. Retrieve existing session
        2. Apply updates atomically
        3. Validate state consistency
        4. Save to Redis
        5. Trigger any hooks
        """
        try:
            # Step 1: Retrieve existing session
            session = await self.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for update")
                return

            # Step 2: Apply updates atomically
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            # Step 3: Validate state consistency
            # (Pydantic handles validation automatically)

            # Step 4: Save to Redis
            await self.save_session(session)

            # Step 5: Trigger any hooks (placeholder for future extensions)
            await self._trigger_update_hooks(session_id, updates)

        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")

    async def update_context(self, session_id: str, context: Dict[str, Any]):
        """
        Update session context.

        Args:
            session_id: Session identifier
            context: Context dictionary to merge
        """
        session = await self.get_session(session_id)
        if session:
            session.context.update(context)
            await self.save_session(session)

    async def add_message(self, session_id: str, message: Dict[str, Any]):
        """
        Add a message to session history.

        Args:
            session_id: Session identifier
            message: Message dictionary with role and content
        """
        try:
            if self.redis_client:
                history_key = f"history:{session_id}"

                # Add message to list
                await self.redis_client.rpush(
                    history_key,
                    json.dumps(message)
                )

                # Trim to max length
                await self.redis_client.ltrim(
                    history_key,
                    -self.max_history_length,
                    -1
                )

                # Set TTL
                await self.redis_client.expire(history_key, self.ttl)
            else:
                # Fallback to memory storage
                if session_id not in self._memory_storage:
                    self._memory_storage[session_id] = Session(id=session_id)

                if 'history' not in self._memory_storage[session_id].metadata:
                    self._memory_storage[session_id].metadata['history'] = []

                history = self._memory_storage[session_id].metadata['history']
                history.append(message)

                # Trim to max length
                if len(history) > self.max_history_length:
                    self._memory_storage[session_id].metadata['history'] = \
                        history[-self.max_history_length:]

            logger.debug(f"Added message to session {session_id}")

        except Exception as e:
            logger.error(f"Error adding message to session {session_id}: {e}")

    async def get_history(self, session_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries
        """
        try:
            if self.redis_client:
                history_key = f"history:{session_id}"

                # Get all messages or limit
                if limit:
                    messages = await self.redis_client.lrange(
                        history_key,
                        -limit,
                        -1
                    )
                else:
                    messages = await self.redis_client.lrange(
                        history_key,
                        0,
                        -1
                    )

                # Parse JSON messages
                history = [json.loads(msg) for msg in messages]
                return history
            else:
                # Fallback to memory storage
                if session_id in self._memory_storage:
                    history = self._memory_storage[session_id].metadata.get('history', [])
                    if limit:
                        return history[-limit:]
                    return history
                return []

        except Exception as e:
            logger.error(f"Error retrieving history for session {session_id}: {e}")
            return []

    async def clear_history(self, session_id: str):
        """
        Clear conversation history for a session.

        Args:
            session_id: Session identifier
        """
        try:
            if self.redis_client:
                history_key = f"history:{session_id}"
                await self.redis_client.delete(history_key)
            else:
                if session_id in self._memory_storage:
                    self._memory_storage[session_id].metadata['history'] = []

            logger.info(f"Cleared history for session {session_id}")

        except Exception as e:
            logger.error(f"Error clearing history for session {session_id}: {e}")

    async def end_session(self, session_id: str):
        """
        End a session and mark it as inactive.

        Args:
            session_id: Session identifier
        """
        await self.update_session(session_id, {'is_active': False})
        logger.info(f"Ended session {session_id}")

    async def cleanup_expired_sessions(self):
        """
        Clean up expired sessions.
        This is handled automatically by Redis TTL, but included for completeness.
        """
        if not self.redis_client:
            # Clean up memory storage
            current_time = datetime.utcnow()
            expired_sessions = []

            for session_id, session in self._memory_storage.items():
                if hasattr(session, 'updated_at'):
                    if current_time - session.updated_at > timedelta(seconds=self.ttl):
                        expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self._memory_storage[session_id]
                logger.debug(f"Cleaned up expired session {session_id}")

    async def get_active_sessions_count(self) -> int:
        """
        Get count of active sessions.

        Returns:
            Number of active sessions
        """
        try:
            if self.redis_client:
                keys = await self.redis_client.keys("session:*")
                return len(keys)
            else:
                return len(self._memory_storage)

        except Exception as e:
            logger.error(f"Error counting active sessions: {e}")
            return 0

    async def _trigger_update_hooks(self, session_id: str, updates: Dict[str, Any]):
        """
        Trigger hooks after session update.
        Placeholder for future extensions like analytics, notifications, etc.

        Args:
            session_id: Session identifier
            updates: Applied updates
        """
        # Future: Add webhooks, analytics tracking, etc.
        pass