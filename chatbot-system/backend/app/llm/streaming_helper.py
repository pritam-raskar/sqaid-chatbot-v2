"""
Streaming Helper - Provider-agnostic streaming utility.
Ensures consistent streaming behavior across all LLM providers.
"""
import logging
from typing import AsyncGenerator, Dict, Any, List
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class StreamingHelper:
    """
    Centralized streaming helper for response formatting.

    This class provides a single entry point for streaming responses
    across all LLM providers, ensuring consistent behavior regardless
    of which provider is being used.
    """

    @staticmethod
    async def stream_response_without_tools(
        provider: BaseLLMProvider,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream response WITHOUT tools for any provider.

        This is the ONLY method agents should use for response formatting.
        All providers MUST implement stream_completion_without_tools().

        This method:
        1. Validates that the provider implements the required interface
        2. Calls the provider's stream_completion_without_tools() method
        3. Extracts content from chunks and yields as strings
        4. Handles errors gracefully

        Args:
            provider: Any LLM provider (must implement BaseLLMProvider)
            messages: Conversation messages including tool results
            **kwargs: Provider-specific parameters (model, temperature, etc.)

        Yields:
            String chunks of content as they arrive

        Raises:
            NotImplementedError: If provider doesn't implement required method

        Example:
            async for chunk in StreamingHelper.stream_response_without_tools(
                provider=llm_provider,
                messages=messages,
                model="claude-3-5-sonnet-20241022",
                temperature=0.0
            ):
                print(chunk, end="", flush=True)
        """
        provider_name = provider.__class__.__name__
        logger.info(f"🌊 StreamingHelper: Using {provider_name} for response formatting")

        # Validate provider has required method (enforced by base class)
        if not hasattr(provider, 'stream_completion_without_tools'):
            error_msg = (
                f"{provider_name} does not implement stream_completion_without_tools(). "
                f"All providers must implement this method per BaseLLMProvider interface."
            )
            logger.error(error_msg)
            raise NotImplementedError(error_msg)

        try:
            # Call provider's implementation
            chunk_count = 0
            async for chunk in provider.stream_completion_without_tools(messages, **kwargs):
                content = chunk.get("content", "")
                if content:
                    chunk_count += 1
                    yield content

            logger.info(f"✅ StreamingHelper: Streamed {chunk_count} chunks from {provider_name}")

        except Exception as e:
            logger.error(f"❌ StreamingHelper: Error streaming from {provider_name}: {e}", exc_info=True)
            # Re-raise to let caller handle the error
            raise
