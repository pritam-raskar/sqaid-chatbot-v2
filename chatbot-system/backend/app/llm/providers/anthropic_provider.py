"""
Anthropic (Claude) LLM Provider
"""
from typing import Dict, List, Any, Optional, AsyncGenerator
import httpx
import logging
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic API provider for Claude models
    Supports Claude 3 Opus, Sonnet, Haiku, and Claude 2.1
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60.0,
        max_retries: int = 3
    ):
        """
        Initialize Anthropic provider

        Args:
            api_key: Anthropic API key
            model: Model name (claude-3-opus, claude-3-sonnet, etc.)
            base_url: Anthropic API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = None

    async def connect(self) -> bool:
        """Initialize Anthropic client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                }
            )
            logger.info(f"Anthropic provider initialized with model: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Anthropic client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("Anthropic provider disconnected")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion using Anthropic Claude

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Dictionary with response and metadata
        """
        try:
            # Convert messages to Anthropic format
            # Anthropic expects system message separate
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            payload = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            if system_message:
                payload["system"] = system_message

            # Add any additional parameters
            payload.update(kwargs)

            response = await self.client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract text content
            content = ""
            if data.get("content"):
                for block in data["content"]:
                    if block.get("type") == "text":
                        content += block.get("text", "")

            return {
                "content": content,
                "role": data.get("role", "assistant"),
                "stop_reason": data.get("stop_reason"),
                "usage": data.get("usage", {}),
                "model": data.get("model"),
                "message_id": data.get("id")
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Anthropic API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            raise

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from Anthropic Claude

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Dictionary with streamed content chunks
        """
        try:
            # Convert messages to Anthropic format
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            payload = {
                "model": self.model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }

            if system_message:
                payload["system"] = system_message

            payload.update(kwargs)

            async with self.client.stream(
                "POST",
                f"{self.base_url}/messages",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        try:
                            import json
                            data = json.loads(data_str)

                            event_type = data.get("type")

                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {
                                        "content": delta.get("text", ""),
                                        "done": False
                                    }

                            elif event_type == "message_stop":
                                yield {
                                    "content": "",
                                    "done": True,
                                    "stop_reason": data.get("stop_reason")
                                }

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}")
            raise

    async def close(self) -> None:
        """Close connections and clean up resources"""
        await self.disconnect()

    def supports_streaming(self) -> bool:
        """Check if the provider supports streaming responses"""
        return True

    def supports_function_calling(self) -> bool:
        """Check if the provider supports function/tool calling"""
        return True  # Claude 3 models support tools

    def get_available_models(self) -> List[str]:
        """Get list of available Anthropic models"""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0"
        ]

    async def chat_completion_with_tools(self,
                                        messages: List[Dict[str, str]],
                                        tools: Optional[List[Dict[str, Any]]] = None,
                                        **kwargs) -> Dict[str, Any]:
        """
        Generate a chat completion with tool/function calling support.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: List of tool definitions in Anthropic format
            **kwargs: Additional parameters

        Returns:
            Dictionary containing the response and tool calls if any
        """
        try:
            # Extract system message if present
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content")
                else:
                    # Ensure content is properly formatted
                    content = msg.get("content")

                    # If content is a string and we're using tools, format it as a content block
                    if isinstance(content, str) and tools:
                        content = [{"type": "text", "text": content}]

                    anthropic_messages.append({
                        "role": msg.get("role"),
                        "content": content
                    })

            payload = {
                "model": kwargs.get("model", self.model),  # Use provided model or default
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.0)
            }

            if system_message:
                payload["system"] = system_message

            # Add tools if provided
            if tools:
                payload["tools"] = tools

            response = await self.client.post(
                f"{self.base_url}/messages",
                json=payload
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Anthropic tool calling failed: {e}")
            # Fallback to regular completion
            return await self.chat_completion(messages, **kwargs)

    async def stream_completion_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion with tool calling support.

        Note: This is for the FINAL response after tools have been executed.
        Tool calls themselves cannot be streamed (they're structured data).

        Args:
            messages: List of message dictionaries
            tools: List of tool definitions in Anthropic format
            **kwargs: Additional parameters (model, temperature, etc.)

        Yields:
            Dictionary with streamed content chunks
        """
        try:
            # Extract system message
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content")
                else:
                    # Handle content formatting
                    content = msg.get("content")
                    if isinstance(content, str) and tools:
                        content = [{"type": "text", "text": content}]

                    anthropic_messages.append({
                        "role": msg.get("role"),
                        "content": content
                    })

            payload = {
                "model": kwargs.get("model", self.model),  # Use provided model or default
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.0),
                "stream": True
            }

            if system_message:
                payload["system"] = system_message

            # Add tools if provided
            if tools:
                payload["tools"] = tools

            async with self.client.stream(
                "POST",
                f"{self.base_url}/messages",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]

                        try:
                            import json
                            data = json.loads(data_str)
                            event_type = data.get("type")

                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {
                                        "content": delta.get("text", ""),
                                        "done": False
                                    }

                            elif event_type == "message_stop":
                                yield {
                                    "content": "",
                                    "done": True,
                                    "stop_reason": data.get("stop_reason")
                                }

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Streaming with tools failed: {e}")
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
            # Extract system message
            system_message = None
            anthropic_messages = []

            for msg in messages:
                if msg.get("role") == "system":
                    system_message = msg.get("content")
                else:
                    # Handle content formatting
                    content = msg.get("content")
                    anthropic_messages.append({
                        "role": msg.get("role"),
                        "content": content
                    })

            payload = {
                "model": kwargs.get("model", self.model),
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.0),
                "stream": True
                # ✅ CRITICAL: NO tools in payload - prevents unwanted tool calls
            }

            if system_message:
                payload["system"] = system_message

            async with self.client.stream(
                "POST",
                f"{self.base_url}/messages",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]

                        try:
                            import json
                            data = json.loads(data_str)
                            event_type = data.get("type")

                            if event_type == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {
                                        "content": delta.get("text", ""),
                                        "done": False
                                    }

                            elif event_type == "message_stop":
                                yield {
                                    "content": "",
                                    "done": True,
                                    "stop_reason": data.get("stop_reason")
                                }

                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Anthropic streaming (no tools) failed: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "anthropic",
            "model": self.model,
            "base_url": self.base_url,
            "supports_streaming": True,
            "supports_functions": True,
            "context_window": 200000 if "claude-3" in self.model else 100000
        }
