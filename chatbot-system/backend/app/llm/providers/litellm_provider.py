"""
LiteLLM Provider - Unified interface for 100+ LLM providers
"""
from typing import Dict, List, Any, Optional, AsyncGenerator
import logging
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class LiteLLMProvider(BaseLLMProvider):
    """
    LiteLLM provider for unified access to multiple LLM APIs
    Supports OpenAI, Anthropic, Cohere, Replicate, Hugging Face, and 100+ more
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = 60.0,
        **kwargs
    ):
        """
        Initialize LiteLLM provider

        Args:
            model: Model identifier (e.g., "gpt-4", "claude-3-opus", "command-nightly")
            api_key: API key for the provider
            api_base: Custom API base URL
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific parameters
        """
        super().__init__()
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout
        self.extra_params = kwargs
        self.litellm = None

    async def connect(self) -> bool:
        """Initialize LiteLLM"""
        try:
            import litellm
            self.litellm = litellm

            # Set API key if provided
            if self.api_key:
                # LiteLLM auto-detects provider from model name
                if "gpt" in self.model.lower():
                    litellm.openai_key = self.api_key
                elif "claude" in self.model.lower():
                    litellm.anthropic_key = self.api_key
                elif "command" in self.model.lower():
                    litellm.cohere_key = self.api_key

            # Set custom API base if provided
            if self.api_base:
                litellm.api_base = self.api_base

            logger.info(f"LiteLLM provider initialized with model: {self.model}")
            return True

        except ImportError:
            logger.error("LiteLLM not installed. Install with: pip install litellm")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize LiteLLM provider: {e}")
            return False

    async def disconnect(self) -> None:
        """Close LiteLLM provider"""
        self.litellm = None
        logger.info("LiteLLM provider disconnected")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion using LiteLLM

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Dictionary with response and metadata
        """
        try:
            if not self.litellm:
                raise Exception("LiteLLM not initialized")

            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }

            if max_tokens:
                params["max_tokens"] = max_tokens

            # Add extra parameters
            params.update(self.extra_params)
            params.update(kwargs)

            # Call LiteLLM completion
            response = await self.litellm.acompletion(**params)

            # Extract response
            choice = response.choices[0]

            return {
                "content": choice.message.content,
                "role": choice.message.role,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if hasattr(response, "usage") else {},
                "model": response.model,
                "message_id": response.id
            }

        except Exception as e:
            logger.error(f"LiteLLM chat completion failed: {e}")
            raise

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from LiteLLM

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Dictionary with streamed content chunks
        """
        try:
            if not self.litellm:
                raise Exception("LiteLLM not initialized")

            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }

            if max_tokens:
                params["max_tokens"] = max_tokens

            params.update(self.extra_params)
            params.update(kwargs)

            # Stream completion
            response = await self.litellm.acompletion(**params)

            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]

                    # Check if delta has content
                    if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                        content = choice.delta.content
                        if content:
                            yield {
                                "content": content,
                                "done": False
                            }

                    # Check if finished
                    if choice.finish_reason:
                        yield {
                            "content": "",
                            "done": True,
                            "finish_reason": choice.finish_reason
                        }

        except Exception as e:
            logger.error(f"LiteLLM streaming failed: {e}")
            raise

    async def stream_completion_without_tools(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream completion WITHOUT tools - for response formatting only.
        Prevents unwanted tool calls during final response generation.
        """
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.0),
                "stream": True
                # ✅ CRITICAL: NO tools parameter - prevents unwanted tool calls
            }

            if self.api_key:
                params["api_key"] = self.api_key
            if self.api_base:
                params["api_base"] = self.api_base

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in ["model", "messages", "temperature", "stream"]:
                    params[key] = value

            # LiteLLM unified streaming (supports 100+ providers)
            response = await self.litellm.acompletion(**params)

            async for chunk in response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    if hasattr(delta, 'content') and delta.content:
                        yield {
                            "content": delta.content,
                            "done": False
                        }

                    if choice.finish_reason:
                        yield {
                            "content": "",
                            "done": True,
                            "finish_reason": choice.finish_reason
                        }

        except Exception as e:
            logger.error(f"LiteLLM streaming (no tools) failed: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        # Try to detect provider from model name
        provider = "unknown"
        if "gpt" in self.model.lower():
            provider = "openai"
        elif "claude" in self.model.lower():
            provider = "anthropic"
        elif "command" in self.model.lower():
            provider = "cohere"
        elif "llama" in self.model.lower():
            provider = "replicate"

        return {
            "provider": f"litellm ({provider})",
            "model": self.model,
            "api_base": self.api_base,
            "supports_streaming": True,
            "supports_functions": "gpt" in self.model.lower()
        }

    @staticmethod
    def get_supported_models() -> List[str]:
        """Get list of supported models"""
        return [
            # OpenAI
            "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo",
            # Anthropic
            "claude-3-opus", "claude-3-sonnet", "claude-3-haiku", "claude-2.1",
            # Cohere
            "command-nightly", "command-light",
            # And 100+ more...
        ]
