"""
WebSocket Handler for real-time chat communication.
Manages WebSocket connections and message streaming.
"""

import json
import asyncio
import logging
import hashlib
from typing import Dict, Optional, Set, List, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_sessions: Dict[str, str] = {}  # connection_id -> session_id

    async def connect(self, websocket: WebSocket, connection_id: str, session_id: str):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_sessions[connection_id] = session_id
        logger.info(f"WebSocket connected: {connection_id} for session {session_id}")

    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            del self.connection_sessions[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_message(self, connection_id: str, message: dict):
        """Send a message to a specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Broadcast a message to all connections except the excluded one."""
        for connection_id, websocket in self.active_connections.items():
            if connection_id != exclude:
                await websocket.send_json(message)


class WebSocketHandler:
    """
    Handles WebSocket connections for real-time chat.
    Manages message processing and response streaming.
    """

    def __init__(self, session_manager, llm_provider=None, tool_registry=None, settings=None):
        """
        Initialize WebSocket handler.

        Args:
            session_manager: SessionManager instance
            llm_provider: LLM provider for generating responses
            tool_registry: Tool registry with all available tools (REST, DB, SOAP)
            settings: Optional AppSettings for feature flags
        """
        self.session_manager = session_manager
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.settings = settings
        self.connection_manager = ConnectionManager()
        self.heartbeat_interval = 30  # seconds
        self.message_handlers = {
            'chat': self._handle_chat_message,
            'ping': self._handle_ping,
            'context_update': self._handle_context_update,
            'filter_request': self._handle_filter_request,
        }

        # Check feature flag for LangGraph
        use_langgraph = False
        if settings:
            use_langgraph = getattr(settings, 'use_langgraph', False)

        self.agent = None
        self.langgraph_orchestrator = None

        if tool_registry and llm_provider:
            if use_langgraph:
                # Initialize LangGraph Orchestrator (Phase 5)
                try:
                    from app.intelligence.langgraph_orchestrator import LangGraphOrchestrator
                    from app.intelligence.agents.agent_registry import AgentRegistry

                    logger.info("🚀 Initializing LangGraph Orchestrator (USE_LANGGRAPH=true)...")

                    agent_registry = AgentRegistry()
                    self.langgraph_orchestrator = LangGraphOrchestrator(
                        llm_provider=llm_provider,
                        tool_registry=tool_registry,
                        agent_registry=agent_registry,
                        settings=settings,
                        session_manager=session_manager
                    )

                    logger.info(f"✅ LangGraph Orchestrator initialized with {len(self.langgraph_orchestrator.get_available_tools())} tools")

                    # Log available tools (first 5)
                    for tool_desc in self.langgraph_orchestrator.get_tool_descriptions()[:5]:
                        logger.info(f"  {tool_desc}")

                except Exception as e:
                    logger.error(f"❌ Failed to initialize LangGraph Orchestrator: {e}", exc_info=True)
                    logger.info("⚠️ Falling back to Universal Agent...")
                    use_langgraph = False

            # Initialize Universal Agent if not using LangGraph or fallback
            if not use_langgraph:
                try:
                    from app.intelligence.universal_agent import UniversalAgent

                    # Create universal agent that works with any provider
                    self.agent = UniversalAgent(
                        llm_provider=llm_provider,
                        tool_registry=tool_registry,
                        session_manager=session_manager
                    )
                    logger.info(f"✅ Universal agent initialized with {len(self.agent.get_available_tools())} tools")

                    # Log available tools (first 5)
                    for tool_desc in self.agent.get_tool_descriptions()[:5]:
                        logger.info(f"  {tool_desc}")

                except Exception as e:
                    logger.error(f"❌ Failed to initialize Universal Agent: {e}", exc_info=True)

        # Keep intent_router for backwards compatibility
        self.intent_router = None

    async def handle_connection(self, websocket: WebSocket, session_id: str = None):
        """
        Handle a WebSocket connection lifecycle.

        Steps:
        1. Accept WebSocket connection
        2. Authenticate user token
        3. Create/retrieve session
        4. Start message listener loop
        5. Handle disconnection gracefully
        """
        connection_id = str(uuid.uuid4())

        try:
            # Step 1: Accept WebSocket connection
            await self.connection_manager.connect(websocket, connection_id, session_id)

            # Step 2: Authenticate user token (placeholder for now)
            # In production, extract and validate JWT from query params or headers
            authenticated = await self._authenticate_connection(websocket)
            if not authenticated:
                await websocket.close(code=1008, reason="Authentication failed")
                return

            # Step 3: Create/retrieve session
            if not session_id:
                session_id = str(uuid.uuid4())

            session = await self.session_manager.get_or_create_session(session_id)

            # Send welcome message
            await self.connection_manager.send_message(connection_id, {
                'type': 'connection_established',
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(connection_id)
            )

            # Step 4: Start message listener loop
            await self._message_listener(websocket, connection_id, session)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected normally: {connection_id}")
        except Exception as e:
            logger.error(f"WebSocket error for {connection_id}: {e}")
        finally:
            # Step 5: Handle disconnection gracefully
            self.connection_manager.disconnect(connection_id)
            if 'heartbeat_task' in locals():
                heartbeat_task.cancel()

    async def _authenticate_connection(self, websocket: WebSocket) -> bool:
        """
        Authenticate the WebSocket connection.

        In production, this would validate JWT tokens.
        """
        # Placeholder - always return True for development
        return True

    async def _message_listener(self, websocket: WebSocket, connection_id: str, session):
        """Listen for messages from the WebSocket."""
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()

                # Process the message
                await self.process_message(data, session, connection_id)

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError as e:
                await self.connection_manager.send_message(connection_id, {
                    'type': 'error',
                    'message': f'Invalid JSON: {str(e)}'
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await self.connection_manager.send_message(connection_id, {
                    'type': 'error',
                    'message': 'Internal server error'
                })

    async def process_message(self, message: dict, session, connection_id: str):
        """
        Process incoming WebSocket message.

        Steps:
        1. Parse message type and content
        2. Add to session history
        3. Route to appropriate handler
        4. Stream response back
        5. Update session state
        """
        # Step 1: Parse message type and content
        message_type = message.get('type', 'chat')
        content = message.get('content', '')
        message_id = message.get('id', str(uuid.uuid4()))

        logger.debug(f"Processing message: type={message_type}, id={message_id}")

        # Step 2: Add to session history
        if message_type == 'chat':
            await self.session_manager.add_message(session.id, {
                'role': 'user',
                'content': content,
                'timestamp': datetime.utcnow().isoformat()
            })

        # Step 3: Route to appropriate handler
        handler = self.message_handlers.get(message_type, self._handle_unknown)

        try:
            # Step 4: Stream response back
            response = await handler(message, session, connection_id)

            # Step 5: Update session state
            if response and message_type == 'chat':
                await self.session_manager.add_message(session.id, {
                    'role': 'assistant',
                    'content': response.get('content', ''),
                    'timestamp': datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"Error handling {message_type} message: {e}")
            await self.connection_manager.send_message(connection_id, {
                'type': 'error',
                'message': f'Failed to process {message_type} message',
                'id': message_id
            })

    async def stream_response(self, response: str, connection_id: str, message_id: str = None):
        """
        Stream response to client in chunks while preserving markdown formatting.

        Steps:
        1. Chunk response intelligently (preserve newlines and markdown)
        2. Send each chunk with type indicator
        3. Handle backpressure
        4. Send completion signal
        """
        # Get streaming configuration from settings
        chunk_size = self.settings.llm_streaming_chunk_size if self.settings else 5
        delay_ms = self.settings.llm_streaming_delay_ms if self.settings else 50

        # Step 1: Chunk response while preserving markdown structure
        # Split by lines first to preserve formatting
        lines = response.split('\n')
        chunks = []
        current_chunk = []
        word_count = 0

        for line in lines:
            # If line is a list item or heading, keep it intact
            if line.strip().startswith(('#', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                # Flush current chunk if it has content
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    word_count = 0
                # Add the list item/heading as its own chunk with newline
                chunks.append(line + '\n')
            else:
                # Split line into words
                words = line.split()
                for word in words:
                    current_chunk.append(word)
                    word_count += 1

                    if word_count >= chunk_size:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = []
                        word_count = 0

                # Add newline at end of line if there's content
                if words:
                    # FIXED: Flush chunk before newline to prevent concatenation
                    if current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = []
                        word_count = 0
                    # Add newline as separate chunk
                    chunks.append('\n')

        # Add any remaining content
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        # Generate assistant message ID if not already an assistant ID
        if message_id and not message_id.startswith('assistant_'):
            assistant_msg_id = f"assistant_{message_id}"
        else:
            assistant_msg_id = message_id or str(uuid.uuid4())

        # DEBUG: Log full response and chunks
        logger.info("=" * 80)
        logger.info("📤 [STREAMING] Final Response:")
        logger.info("-" * 80)
        logger.info(response)
        logger.info("=" * 80)
        logger.info(f"📦 [STREAMING] Total chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks[:10]):  # Log first 10 chunks
            logger.info(f"  Chunk {i}: {repr(chunk)}")
        logger.info("=" * 80)

        # Step 2: Send each chunk with type indicator
        for i, chunk in enumerate(chunks):
            # Ensure proper spacing between chunks when concatenated on frontend
            # Add trailing space to non-newline chunks that don't already end with whitespace
            if chunk and chunk != '\n' and not chunk.endswith((' ', '\n')):
                chunk = chunk + ' '

            await self.connection_manager.send_message(connection_id, {
                'type': 'stream_chunk',
                'content': chunk,
                'chunk_index': i,
                'id': assistant_msg_id
            })

            # Step 3: Handle backpressure (configurable delay)
            await asyncio.sleep(delay_ms / 1000.0)  # Convert ms to seconds

        # Step 4: Send completion signal
        await self.connection_manager.send_message(connection_id, {
            'type': 'stream_complete',
            'id': assistant_msg_id
        })

    async def stream_llm_response(self, messages: list, connection_id: str, message_id: str = None):
        """
        Stream LLM response tokens in real-time.

        This method uses the LLM provider's streaming capability to send tokens
        as they arrive from the API, providing immediate feedback to users.

        Args:
            messages: List of messages for LLM context
            connection_id: WebSocket connection ID
            message_id: Message ID for tracking (user message ID)

        Returns:
            Complete response text
        """
        if not self.llm_provider or not self.llm_provider.supports_streaming():
            logger.warning("LLM provider doesn't support streaming, falling back to non-streaming")
            response = await self.llm_provider.chat_completion(messages=messages, temperature=0.7)
            # Generate new ID for assistant response
            assistant_msg_id = f"assistant_{message_id}" if message_id else str(uuid.uuid4())
            await self.stream_response(response.get('content', ''), connection_id, assistant_msg_id)
            return response.get('content', '')

        try:
            full_response = ""
            # Generate new ID for assistant response (different from user message ID)
            assistant_msg_id = f"assistant_{message_id}" if message_id else str(uuid.uuid4())

            # Stream tokens from LLM provider
            async for chunk in self.llm_provider.stream_completion(
                messages=messages,
                temperature=0.7
            ):
                content = chunk.get('content', '')
                if content:
                    full_response += content

                    # Send token immediately to client with assistant message ID
                    await self.connection_manager.send_message(connection_id, {
                        'type': 'stream_chunk',
                        'content': content,
                        'id': assistant_msg_id
                    })

                # Check if done
                if chunk.get('done'):
                    break

            # Send completion signal
            await self.connection_manager.send_message(connection_id, {
                'type': 'stream_complete',
                'id': assistant_msg_id
            })

            return full_response

        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            # Fallback to non-streaming
            response = await self.llm_provider.chat_completion(messages=messages, temperature=0.7)
            await self.stream_response(response.get('content', ''), connection_id, message_id)
            return response.get('content', '')

    async def _handle_chat_message(self, message: dict, session, connection_id: str):
        """Handle chat messages with intelligent routing."""
        content = message.get('content', '')
        message_id = message.get('id')
        page_context = message.get('context', {})  # Parent application context

        # FEATURE FLAG CHECK #1: Check if visualizations are enabled
        enable_visualizations = False
        visualization_delay_ms = 100
        if self.settings:
            enable_visualizations = getattr(self.settings, 'enable_visualizations', False)
            visualization_delay_ms = getattr(self.settings, 'visualization_delay_ms', 100)

        # Send acknowledgment
        await self.connection_manager.send_message(connection_id, {
            'type': 'message_received',
            'id': message_id
        })

        # Check if LangGraph Orchestrator is available (Phase 5)
        if hasattr(self, 'langgraph_orchestrator') and self.langgraph_orchestrator:
            try:
                # Use LangGraph multi-agent orchestration with streaming
                logger.info(f"🚀 Processing message with LangGraph Orchestrator: {content[:50]}...")

                # Stream workflow execution
                async for event in self.langgraph_orchestrator.stream_workflow(
                    message=content,
                    session_id=session.id,
                    context=page_context
                ):
                    event_type = event.get('type')

                    if event_type == 'node_update':
                        # Send node execution updates to client
                        node_name = event.get('node', 'unknown')
                        state_update = event.get('state_update', {})

                        # Check for final response
                        if 'final_response' in state_update:
                            response_text = state_update['final_response']

                            # FEATURE FLAG CHECK #2: Extract visualization if enabled
                            clean_text = response_text
                            if enable_visualizations:
                                try:
                                    from app.prompts.visualization_prompt import VisualizationPromptBuilder
                                    viz_builder = VisualizationPromptBuilder()
                                    clean_text, _ = viz_builder.extract_text_and_visualization(response_text)
                                    logger.info(f"Extracted clean text (removed JSON): {len(clean_text)} chars vs {len(response_text)} chars")
                                except Exception as e:
                                    logger.warning(f"Failed to extract visualization from text: {e}")
                                    clean_text = response_text

                            # Stream the clean text (without visualization JSON)
                            await self.stream_response(clean_text, connection_id, message_id)

                            # Process visualization if enabled
                            if enable_visualizations:
                                asyncio.create_task(
                                    self._process_visualization(
                                        response_text, connection_id, message_id, visualization_delay_ms
                                    )
                                )

                            return {'content': clean_text}

                        # Send progress update
                        await self.connection_manager.send_message(connection_id, {
                            'type': 'workflow_progress',
                            'node': node_name,
                            'id': message_id
                        })

                    elif event_type == 'error':
                        error_msg = event.get('error', 'Unknown error')
                        logger.error(f"❌ LangGraph workflow error: {error_msg}")

                        await self.connection_manager.send_message(connection_id, {
                            'type': 'error',
                            'message': f'Workflow error: {error_msg}',
                            'id': message_id
                        })

                        return {'content': f'Error: {error_msg}'}

                # If we got here without final_response, return a default
                return {'content': 'Query processed but no response generated.'}

            except Exception as e:
                logger.error(f"❌ LangGraph orchestrator error: {e}", exc_info=True)
                logger.info("⚠️ Falling back to Universal Agent...")

        # Check if Universal Agent is available for tool calling
        if hasattr(self, 'agent') and self.agent:
            try:
                # Use universal agent with tool calling
                logger.info(f"✅ Processing message with Universal Agent: {content[:50]}...")

                agent_response = await self.agent.process_message(
                    message=content,
                    session_id=session.id
                )

                response_text = agent_response.get('content', '')

                # Log if tools were used
                if agent_response.get('tool_calls'):
                    logger.info(f"Tools used: {len(agent_response.get('tool_calls', []))} tool(s)")
                    for tool_result in agent_response.get('tool_calls', []):
                        logger.debug(f"  - {tool_result.get('tool', 'unknown')}: {tool_result.get('result', '')[:100]}...")

                # Extract visualization if enabled
                clean_text = response_text
                if enable_visualizations:
                    try:
                        from app.prompts.visualization_prompt import VisualizationPromptBuilder
                        viz_builder = VisualizationPromptBuilder()
                        clean_text, _ = viz_builder.extract_text_and_visualization(response_text)
                        logger.info(f"Extracted clean text (removed JSON): {len(clean_text)} chars vs {len(response_text)} chars")
                    except Exception as e:
                        logger.warning(f"Failed to extract visualization from text: {e}")
                        clean_text = response_text

                # Stream the clean text (without visualization JSON)
                await self.stream_response(clean_text, connection_id, message_id)

                # Process visualization if enabled
                if enable_visualizations:
                    asyncio.create_task(
                        self._process_visualization(
                            response_text, connection_id, message_id, visualization_delay_ms
                        )
                    )

                return {'content': clean_text}

            except Exception as e:
                logger.error(f"❌ Universal agent error: {e}")
                # Fallback to direct LLM
                logger.info("⚠️ Falling back to direct LLM call")

        # Fallback: Generate response using LLM directly
        if self.llm_provider:
            try:
                # Get conversation history
                history = await self.session_manager.get_history(session.id)

                # Prepare messages for LLM
                messages = [
                    {'role': msg['role'], 'content': msg['content']}
                    for msg in history
                ]
                messages.append({'role': 'user', 'content': content})

                # Check if LLM streaming is enabled
                enable_streaming = self.settings.enable_llm_streaming if self.settings else True

                if enable_streaming:
                    # Use real-time LLM token streaming
                    logger.info("🌊 Streaming LLM response in real-time...")
                    response_text = await self.stream_llm_response(
                        messages=messages,
                        connection_id=connection_id,
                        message_id=message_id
                    )
                    logger.info(f"✅ Streamed {len(response_text)} characters")

                    # FEATURE FLAG CHECK #2: Process visualization if enabled
                    if enable_visualizations:
                        asyncio.create_task(
                            self._process_visualization(
                                response_text, connection_id, message_id, visualization_delay_ms
                            )
                        )

                    return {'content': response_text}
                else:
                    # Traditional non-streaming mode
                    logger.info("📦 Getting complete LLM response...")
                    response = await self.llm_provider.chat_completion(
                        messages=messages,
                        temperature=0.7
                    )

                    # Log the response for debugging
                    logger.info(f"LLM Response: {response.get('content', '')[:200]}...")

                    response_text = response.get('content', '')

                    # Extract visualization if enabled
                    clean_text = response_text
                    if enable_visualizations:
                        try:
                            from app.prompts.visualization_prompt import VisualizationPromptBuilder
                            viz_builder = VisualizationPromptBuilder()
                            clean_text, _ = viz_builder.extract_text_and_visualization(response_text)
                            logger.info(f"Extracted clean text (removed JSON): {len(clean_text)} chars vs {len(response_text)} chars")
                        except Exception as e:
                            logger.warning(f"Failed to extract visualization from text: {e}")
                            clean_text = response_text

                    # Stream the clean text (word-based chunking)
                    await self.stream_response(
                        clean_text,
                        connection_id,
                        message_id
                    )

                    # Process visualization if enabled
                    if enable_visualizations:
                        asyncio.create_task(
                            self._process_visualization(
                                response_text, connection_id, message_id, visualization_delay_ms
                            )
                        )

                    return {'content': clean_text}

            except Exception as e:
                logger.error(f"LLM error: {e}")
                error_response = "I apologize, but I'm having trouble generating a response right now."
                await self.stream_response(error_response, connection_id, message_id)
        else:
            # No LLM provider configured - send informative error
            logger.warning(f"No LLM provider available for message: {content[:50]}")
            error_response = (
                "The chatbot is currently running without an LLM provider. "
                "Please configure an LLM provider (OpenAI, Anthropic, or Eliza) to enable chat functionality. "
                f"You sent: '{content}'"
            )
            await self.stream_response(error_response, connection_id, message_id)
            return {'content': error_response}

    async def _handle_with_intelligence(
        self,
        content: str,
        session,
        page_context: dict,
        connection_id: str,
        message_id: str
    ) -> str:
        """
        Handle message using IntentRouter and intelligent query planning

        Args:
            content: User message content
            session: Session object
            page_context: Context from parent application (filters, selections, etc.)
            connection_id: WebSocket connection ID
            message_id: Message ID

        Returns:
            Response text
        """
        # Get conversation history
        history = await self.session_manager.get_history(session.id)

        # Build context for routing
        routing_context = {
            "page_context": page_context,
            "user_info": getattr(session, 'user_info', {}),
            "conversation_history": history,
            "session_id": session.id
        }

        # Enrich query with context if context enricher available
        if hasattr(self, 'context_enricher') and self.context_enricher:
            enriched = await self.context_enricher.enrich_query(
                query=content,
                session_id=session.id,
                user_info=routing_context.get("user_info"),
                page_context=page_context,
                conversation_history=history
            )
            logger.info(f"Context enrichment: {self.context_enricher.get_context_summary(enriched)}")

        # Route query through IntentRouter
        routing_decision = await self.intent_router.route_query(
            query=content,
            context=routing_context
        )

        logger.info(
            f"Routing decision: intent={routing_decision.intent}, "
            f"confidence={routing_decision.confidence:.2f}, "
            f"tools={routing_decision.selected_tools}"
        )

        # If confidence is low, use direct LLM
        if routing_decision.confidence < 0.3:
            logger.warning(f"Low routing confidence ({routing_decision.confidence}), using direct LLM")
            messages = [{'role': msg['role'], 'content': msg['content']} for msg in history]
            messages.append({'role': 'user', 'content': content})

            response = await self.llm_provider.chat_completion(
                messages=messages,
                temperature=0.7
            )
            return response.get('content', '')

        # Execute routing with agent
        execution_result = await self.intent_router.execute_routing(
            query=content,
            context=routing_context
        )

        if execution_result.get('success'):
            return execution_result.get('answer', 'No response generated')
        else:
            error_msg = execution_result.get('error', 'Unknown error')
            logger.error(f"Routing execution failed: {error_msg}")
            return f"I encountered an issue while processing your request: {error_msg}"

    async def _handle_ping(self, message: dict, session, connection_id: str):
        """Handle ping messages for connection health check."""
        await self.connection_manager.send_message(connection_id, {
            'type': 'pong',
            'timestamp': datetime.utcnow().isoformat()
        })

    async def _handle_context_update(self, message: dict, session, connection_id: str):
        """Handle context updates from the client."""
        context = message.get('context', {})

        # Update session context
        await self.session_manager.update_context(session.id, context)

        await self.connection_manager.send_message(connection_id, {
            'type': 'context_updated',
            'id': message.get('id')
        })

    async def _handle_filter_request(self, message: dict, session, connection_id: str):
        """Handle filter generation requests."""
        query = message.get('query', '')
        message_id = message.get('id')

        # This will be implemented with FilterGenerator in later steps
        # For now, return a mock filter
        mock_filter = {
            'filters': [
                {'field': 'status', 'operator': '=', 'value': 'active'}
            ]
        }

        await self.connection_manager.send_message(connection_id, {
            'type': 'filter_generated',
            'filters': mock_filter,
            'id': message_id
        })

        return mock_filter

    async def _handle_unknown(self, message: dict, session, connection_id: str):
        """Handle unknown message types."""
        await self.connection_manager.send_message(connection_id, {
            'type': 'error',
            'message': f"Unknown message type: {message.get('type')}",
            'id': message.get('id')
        })

    async def _heartbeat_loop(self, connection_id: str):
        """Send periodic heartbeat messages to keep connection alive."""
        try:
            while connection_id in self.connection_manager.active_connections:
                await asyncio.sleep(self.heartbeat_interval)
                await self.connection_manager.send_message(connection_id, {
                    'type': 'heartbeat',
                    'timestamp': datetime.utcnow().isoformat()
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

    def _create_data_signature(self, data: List[Dict[str, Any]]) -> str:
        """
        Create a unique signature for visualization data.
        Used to detect visualizations with identical data.

        Args:
            data: List of data points

        Returns:
            MD5 hash signature of the data
        """
        try:
            # Extract only name and value for comparison (ignore metadata like percentage)
            normalized_data = []
            for item in data:
                normalized_item = {
                    'name': str(item.get('name', '')),
                    'value': float(item.get('value', 0))
                }
                normalized_data.append(normalized_item)

            # Sort by name to ensure consistent ordering
            sorted_data = sorted(normalized_data, key=lambda x: x['name'])

            # Create string representation
            data_str = json.dumps(sorted_data, sort_keys=True)

            # Return hash
            signature = hashlib.md5(data_str.encode()).hexdigest()

            # Debug logging
            logger.info(f"📝 Data signature: {signature[:8]}... for data: {sorted_data}")

            return signature
        except Exception as e:
            logger.warning(f"Failed to create data signature: {e}")
            return str(uuid.uuid4())

    def _choose_default_type(self, types: List[str]) -> str:
        """
        Choose the best default chart type from available options.

        Args:
            types: List of available chart types

        Returns:
            Best default type
        """
        # Priority order: bar is most versatile, then pie, line, area, scatter
        priority = ['bar', 'pie', 'line', 'area', 'scatter']
        for preferred in priority:
            if preferred in types:
                return preferred
        return types[0] if types else 'bar'

    def _merge_compatible_visualizations(self, viz_metadata_list: List[Any]) -> List[Dict[str, Any]]:
        """
        Group visualizations with identical data into unified format.

        Args:
            viz_metadata_list: List of VisualizationMetadata objects

        Returns:
            List of unified visualization objects with multiple type options
        """
        try:
            data_groups = {}

            for viz_metadata in viz_metadata_list:
                # Create signature from data
                signature = self._create_data_signature(viz_metadata.data)

                if signature not in data_groups:
                    data_groups[signature] = {
                        'data': viz_metadata.data,
                        'types': [],
                        'configs': {},
                        'metadata': viz_metadata.metadata
                    }

                # Add this chart type as option
                data_groups[signature]['types'].append(viz_metadata.chart_type)
                data_groups[signature]['configs'][viz_metadata.chart_type] = viz_metadata.config

            # Convert to unified format
            unified_viz = []
            for signature, group in data_groups.items():
                default_type = self._choose_default_type(group['types'])

                unified_viz.append({
                    'types': group['types'],
                    'data': group['data'],
                    'defaultType': default_type,
                    'configs': group['configs'],
                    'metadata': group['metadata'],
                    'count': len(group['types'])
                })

                logger.info(f"🔗 Merged {len(group['types'])} chart types for same data: {group['types']}")

            return unified_viz

        except Exception as e:
            logger.error(f"Failed to merge visualizations: {e}")
            # Fallback: return individual visualizations
            return [{
                'types': [viz.chart_type],
                'data': viz.data,
                'defaultType': viz.chart_type,
                'configs': {viz.chart_type: viz.config},
                'metadata': viz.metadata,
                'count': 1
            } for viz in viz_metadata_list]

    async def _process_visualization(
        self,
        response_text: str,
        connection_id: str,
        message_id: str,
        delay_ms: int = 100
    ):
        """
        Extract and send visualization data from LLM response.

        Args:
            response_text: Full LLM response text
            connection_id: WebSocket connection ID
            message_id: User message ID
            delay_ms: Delay in milliseconds before sending visualization

        Steps:
        1. Wait for delay (allows user to start reading text)
        2. Extract visualization metadata from response
        3. Validate and enrich visualization
        4. Send visualization message to client
        """
        try:
            from app.prompts.visualization_prompt import VisualizationPromptBuilder
            from app.intelligence.visualization_extractor import VisualizationExtractor

            # Step 1: Wait for delay (progressive rendering)
            await asyncio.sleep(delay_ms / 1000.0)

            # Step 2: Extract visualization metadata
            prompt_builder = VisualizationPromptBuilder()
            _, viz_data = prompt_builder.extract_text_and_visualization(response_text)

            if not viz_data:
                logger.debug("No visualization data found in response")
                return

            # Step 3: Handle single or multiple visualizations
            viz_extractor = VisualizationExtractor()
            viz_list = viz_data if isinstance(viz_data, list) else [viz_data]

            # Step 4: Validate all visualizations
            valid_viz_metadata = []
            invalid_count = 0

            for idx, viz in enumerate(viz_list):
                viz_metadata = viz_extractor.extract(viz)

                if not viz_metadata or not viz_metadata.is_valid:
                    invalid_count += 1
                    logger.warning(f"Invalid visualization {idx + 1}/{len(viz_list)}: {viz_metadata.error_message if viz_metadata else 'None'}")
                    continue

                valid_viz_metadata.append(viz_metadata)

            if not valid_viz_metadata:
                logger.warning(f"No valid visualizations found ({len(viz_list)} attempted, {invalid_count} invalid)")
                return

            # Step 5: Merge visualizations with identical data
            unified_visualizations = self._merge_compatible_visualizations(valid_viz_metadata)

            logger.info(f"📊 Processed {len(valid_viz_metadata)} visualizations → {len(unified_visualizations)} unified blocks")

            # Step 6: Send unified visualizations
            assistant_msg_id = f"assistant_{message_id}" if message_id else str(uuid.uuid4())

            for idx, unified_viz in enumerate(unified_visualizations):
                # Create unified message format
                viz_message = {
                    'type': 'visualization',
                    'message_id': assistant_msg_id,
                    'data': {
                        'types': unified_viz['types'],
                        'data': unified_viz['data'],
                        'defaultType': unified_viz['defaultType'],
                        'configs': unified_viz['configs'],
                        'metadata': unified_viz.get('metadata', {}),
                        'count': unified_viz['count']
                    }
                }

                logger.info(f"📊 Sending unified visualization {idx + 1}/{len(unified_visualizations)} to message {assistant_msg_id}: types={unified_viz['types']}, points={len(unified_viz['data'])}")

                await self.connection_manager.send_message(connection_id, viz_message)

                logger.info(f"✅ Sent unified visualization with {unified_viz['count']} chart type options: {unified_viz['types']}")

                # Small delay between multiple unified blocks
                if idx < len(unified_visualizations) - 1:
                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error processing visualization: {e}", exc_info=True)