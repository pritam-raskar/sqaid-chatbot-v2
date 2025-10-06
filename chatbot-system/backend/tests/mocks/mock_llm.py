"""Mock LLM Provider for testing"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.llm.base_provider import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing"""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        should_fail: bool = False
    ):
        """
        Initialize mock LLM provider

        Args:
            responses: List of predefined responses
            should_fail: If True, raise exceptions
        """
        super().__init__()
        self.responses = responses or ["This is a mock response"]
        self.should_fail = should_fail
        self.call_count = 0
        self.last_messages = None
        self._is_connected = False

    async def connect(self) -> bool:
        """Mock connection"""
        if self.should_fail:
            return False
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mock chat completion

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Returns:
            Mock response dictionary
        """
        if self.should_fail:
            raise Exception("Mock LLM failure")

        self.last_messages = messages
        response_idx = self.call_count % len(self.responses)
        response_text = self.responses[response_idx]
        self.call_count += 1

        return {
            "content": response_text,
            "role": "assistant",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            },
            "model": "mock-model",
            "message_id": f"mock-{self.call_count}"
        }

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Mock streaming completion

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            **kwargs: Additional parameters

        Yields:
            Mock response chunks
        """
        if self.should_fail:
            raise Exception("Mock LLM streaming failure")

        self.last_messages = messages
        response_idx = self.call_count % len(self.responses)
        response_text = self.responses[response_idx]
        self.call_count += 1

        # Stream response word by word
        words = response_text.split()
        for word in words:
            yield {
                "content": word + " ",
                "done": False
            }

        # Final chunk
        yield {
            "content": "",
            "done": True,
            "finish_reason": "stop"
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get mock model info"""
        return {
            "provider": "mock",
            "model": "mock-model",
            "supports_streaming": True,
            "supports_functions": False
        }
