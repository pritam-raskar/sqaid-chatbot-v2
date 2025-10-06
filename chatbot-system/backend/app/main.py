"""
Main FastAPI application for the Financial Case Management Chatbot.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.core.config import config_loader, get_settings
from app.orchestration import WebSocketHandler, SessionManager
from app.llm.providers import ElizaProvider
from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.tool_initializer import initialize_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global instances
session_manager = None
websocket_handler = None
llm_provider = None
tool_registry = None
tool_initializer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Initialize resources on startup and cleanup on shutdown.
    """
    global session_manager, websocket_handler, llm_provider, tool_registry, tool_initializer

    # Startup
    logger.info("Starting Financial Case Management Chatbot...")

    # Initialize configuration
    config_loader.start_watching()  # Start watching for config changes

    # Initialize Redis/Session Manager
    redis_config = config_loader.get_redis_config().dict()
    session_manager = SessionManager(redis_config)
    await session_manager.connect()

    # Initialize LLM Provider (try multiple providers)
    llm_provider = None

    # Try Anthropic first
    try:
        from app.llm.providers.anthropic_provider import AnthropicProvider
        anthropic_key = get_settings().anthropic_api_key if hasattr(get_settings(), 'anthropic_api_key') else None
        if anthropic_key and anthropic_key.strip():
            llm_provider = AnthropicProvider(
                api_key=anthropic_key,
                model=getattr(get_settings(), 'anthropic_model', 'claude-3-5-haiku-20241022'),
                base_url=getattr(get_settings(), 'anthropic_base_url', 'https://api.anthropic.com/v1'),
                timeout=float(getattr(get_settings(), 'anthropic_timeout', 60)),
                max_retries=int(getattr(get_settings(), 'anthropic_max_retries', 3)),
            )
            await llm_provider.connect()
            logger.info("Anthropic LLM provider initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize Anthropic provider: {e}")

    # Try OpenAI if Anthropic failed
    if not llm_provider:
        try:
            from app.llm.providers.openai_provider import OpenAIProvider
            openai_key = get_settings().openai_api_key if hasattr(get_settings(), 'openai_api_key') else None
            if openai_key and openai_key.strip():
                llm_provider = OpenAIProvider(
                    api_key=openai_key,
                    model=getattr(get_settings(), 'openai_model', 'gpt-4'),
                    base_url=getattr(get_settings(), 'openai_base_url', 'https://api.openai.com/v1'),
                    timeout=getattr(get_settings(), 'openai_timeout', 60),
                    max_retries=getattr(get_settings(), 'openai_max_retries', 3),
                )
                await llm_provider.connect()
                logger.info("OpenAI LLM provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenAI provider: {e}")

    # Try Eliza as last resort
    if not llm_provider:
        try:
            eliza_config = config_loader.get_eliza_config().dict()
            llm_provider = ElizaProvider(eliza_config)
            await llm_provider.connect()
            logger.info("Eliza LLM provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Eliza provider: {e}")

    if not llm_provider:
        logger.warning("Running without LLM support - no provider configured")
        llm_provider = None

    # Initialize Tool Registry and load all tools
    try:
        logger.info("Initializing Tool Registry and loading tools...")
        tool_registry = ToolRegistry(embeddings=None)  # Add embeddings if available
        tool_initializer = await initialize_tools(
            tool_registry=tool_registry,
            embeddings=None,  # Add embeddings model if available
            config_path=None  # Uses default /config path
        )
        logger.info(f"Tool Registry initialized with {len(tool_registry.get_all_tools())} tools")
    except Exception as e:
        logger.error(f"Failed to initialize Tool Registry: {e}", exc_info=True)
        tool_registry = None

    # Initialize WebSocket Handler with tool registry and settings
    websocket_handler = WebSocketHandler(
        session_manager=session_manager,
        llm_provider=llm_provider,
        tool_registry=tool_registry,  # Pass tool registry to handler
        settings=get_settings()  # Pass settings to enable LangGraph if configured
    )

    logger.info("Application startup complete")

    yield  # Application runs

    # Shutdown
    logger.info("Shutting down application...")

    # Cleanup resources
    if llm_provider:
        await llm_provider.close()

    await session_manager.disconnect()
    config_loader.stop_watching()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Financial Case Management Chatbot",
    version="1.0.0",
    description="Intelligent chatbot for financial case management",
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
api_config = config_loader.get_api_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment
    }

    # Check Redis connection
    if session_manager:
        try:
            session_count = await session_manager.get_active_sessions_count()
            health_status["redis"] = "connected"
            health_status["active_sessions"] = session_count
        except:
            health_status["redis"] = "disconnected"

    # Check LLM provider
    if llm_provider:
        try:
            is_healthy = await llm_provider.health_check()
            health_status["llm_provider"] = "healthy" if is_healthy else "unhealthy"
        except:
            health_status["llm_provider"] = "unavailable"
    else:
        health_status["llm_provider"] = "not configured"

    # Feature flags
    health_status["features"] = {
        "visualizations_enabled": settings.enable_visualizations,
        "llm_streaming_enabled": settings.enable_llm_streaming,
        "langgraph_enabled": settings.use_langgraph
    }

    # Visualization configuration (if enabled)
    if settings.enable_visualizations:
        health_status["features"]["visualization_config"] = {
            "min_data_points": settings.visualization_min_data_points,
            "max_data_points": settings.visualization_max_data_points,
            "delay_ms": settings.visualization_delay_ms
        }

    return health_status


# API info endpoint
@app.get("/api/v1/info")
async def api_info():
    """Get API information."""
    return {
        "name": "Financial Case Management Chatbot API",
        "version": "1.0.0",
        "environment": settings.environment,
        "features": {
            "websocket": True,
            "llm_support": llm_provider is not None,
            "session_management": True,
            "data_adapters": ["REST", "PostgreSQL", "Oracle"]  # Will be implemented
        }
    }


# WebSocket endpoint for chat
@app.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket, session_id: str = None):
    """
    WebSocket endpoint for real-time chat communication.

    Args:
        websocket: WebSocket connection
        session_id: Optional session ID to resume existing session
    """
    if not websocket_handler:
        await websocket.close(code=1011, reason="Service temporarily unavailable")
        return

    try:
        await websocket_handler.handle_connection(websocket, session_id)
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Internal server error")


# Session management endpoints
@app.post("/api/v1/sessions")
async def create_session():
    """Create a new chat session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session service unavailable")

    session = session_manager.create_session()
    await session_manager.save_session(session)

    return {
        "session_id": session.id,
        "created_at": session.created_at.isoformat()
    }


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session service unavailable")

    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.id,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "is_active": session.is_active,
        "context": session.context
    }


@app.get("/api/v1/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = None):
    """Get conversation history for a session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session service unavailable")

    history = await session_manager.get_history(session_id, limit)
    return {
        "session_id": session_id,
        "messages": history,
        "count": len(history)
    }


@app.delete("/api/v1/sessions/{session_id}")
async def end_session(session_id: str):
    """End a chat session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session service unavailable")

    await session_manager.end_session(session_id)
    return {"message": "Session ended successfully"}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# Main entry point
if __name__ == "__main__":
    # Get configuration
    api_config = config_loader.get_api_config()

    # Run the application
    uvicorn.run(
        "app.main:app",
        host=api_config.host,
        port=api_config.port,
        reload=settings.environment == "development"#,
        #log_level=(settings.debug and "debug" or "info")
    )