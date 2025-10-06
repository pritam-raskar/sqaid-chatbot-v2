"""
Base LLM Provider Interface
Defines the contract that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All LLM providers must implement this interface.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the LLM service."""
        pass

    @abstractmethod
    async def chat_completion(self,
                            messages: List[Dict[str, str]],
                            **kwargs) -> Dict[str, Any]:
        """
        Generate a chat completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional provider-specific parameters

        Returns:
            Dictionary containing the response
        """
        pass

    @abstractmethod
    async def stream_completion(self,
                              messages: List[Dict[str, str]],
                              **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion responses.

        Args:
            messages: List of message dictionaries
            **kwargs: Additional provider-specific parameters

        Yields:
            Chunks of the response as they become available
        """
        pass

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if the provider supports streaming responses."""
        pass

    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Check if the provider supports function/tool calling."""
        pass

    async def chat_completion_with_tools(self,
                                        messages: List[Dict[str, str]],
                                        tools: Optional[List[Dict[str, Any]]] = None,
                                        **kwargs) -> Dict[str, Any]:
        """
        Generate a chat completion with tool/function calling support.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: List of tool definitions (format depends on provider)
            **kwargs: Additional provider-specific parameters

        Returns:
            Dictionary containing the response and tool calls if any
        """
        if not self.supports_function_calling():
            # Fallback to regular chat completion for providers without tool support
            return await self.chat_completion(messages, **kwargs)

        # Default implementation - providers should override this
        raise NotImplementedError(f"{self.__class__.__name__} must implement chat_completion_with_tools")

    @abstractmethod
    async def stream_completion_without_tools(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream completion WITHOUT tool calling - for response formatting.

        MANDATORY: All providers MUST implement this method.

        This method is used for final response formatting where tools
        should NOT be available to prevent unwanted tool calls.

        Args:
            messages: Conversation messages (including tool results)
            **kwargs: Provider-specific parameters (model, temperature, etc.)

        Yields:
            Dict with 'content' (str) and optionally 'done' (bool)

        Example:
            yield {"content": "text chunk", "done": False}
            yield {"content": "", "done": True}
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources and close connections."""
        pass

    async def health_check(self) -> bool:
        """
        Check if the provider is healthy and responsive.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try a simple completion
            response = await self.chat_completion([
                {"role": "user", "content": "test"}
            ], max_tokens=5)
            return bool(response)
        except Exception:
            return False