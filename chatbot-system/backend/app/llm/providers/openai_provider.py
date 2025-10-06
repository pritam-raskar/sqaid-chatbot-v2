"""
OpenAI LLM Provider
"""
from typing import Dict, List, Any, Optional, AsyncGenerator
import httpx
import logging
from app.llm.base_provider import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider for GPT models
    Supports GPT-4, GPT-3.5-turbo, and other OpenAI models
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_retries: int = 3
    ):
        """
        Initialize OpenAI provider

        Args:
            api_key: OpenAI API key
            model: Model name (gpt-4, gpt-3.5-turbo, etc.)
            base_url: OpenAI API base URL
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
        """Initialize OpenAI client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            logger.info(f"OpenAI provider initialized with model: {self.model}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            return False

    async def disconnect(self) -> None:
        """Close OpenAI client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("OpenAI provider disconnected")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate chat completion using OpenAI

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Dictionary with response and metadata
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            # Add any additional parameters
            payload.update(kwargs)

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]

            return {
                "content": choice["message"]["content"],
                "role": choice["message"]["role"],
                "finish_reason": choice.get("finish_reason"),
                "usage": data.get("usage", {}),
                "model": data.get("model"),
                "message_id": data.get("id")
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"OpenAI API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            raise

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat completion from OpenAI

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Dictionary with streamed content chunks
        """
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": True
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            payload.update(kwargs)

            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            import json
                            data = json.loads(data_str)

                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})

                                if "content" in delta:
                                    yield {
                                        "content": delta["content"],
                                        "done": False
                                    }

                                finish_reason = data["choices"][0].get("finish_reason")
                                if finish_reason:
                                    yield {
                                        "content": "",
                                        "done": True,
                                        "finish_reason": finish_reason
                                    }
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
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
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": messages,
                "temperature": kwargs.get("temperature", 0.0),
                "stream": True
                # ✅ CRITICAL: NO tools in payload - prevents unwanted tool calls
            }

            if kwargs.get("max_tokens"):
                payload["max_tokens"] = kwargs["max_tokens"]

            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str.strip() == "[DONE]":
                            yield {"content": "", "done": True}
                            break

                        try:
                            import json
                            data = json.loads(data_str)

                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})

                                if "content" in delta:
                                    yield {
                                        "content": delta["content"],
                                        "done": False
                                    }

                                finish_reason = data["choices"][0].get("finish_reason")
                                if finish_reason:
                                    yield {
                                        "content": "",
                                        "done": True,
                                        "finish_reason": finish_reason
                                    }
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"OpenAI streaming (no tools) failed: {e}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": "openai",
            "model": self.model,
            "base_url": self.base_url,
            "supports_streaming": True,
            "supports_functions": True
        }
