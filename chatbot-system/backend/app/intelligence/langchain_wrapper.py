"""
LangChain LLM wrapper for Eliza and other providers
"""
from typing import Any, List, Optional, Dict, Mapping
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import Generation, LLMResult
import asyncio
from app.llm.providers.eliza_provider import ElizaProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.anthropic_provider import AnthropicProvider


class ElizaLangChainWrapper(LLM):
    """
    LangChain LLM wrapper for Eliza provider
    Enables Eliza to work with LangChain agents and chains
    """

    eliza_provider: ElizaProvider
    temperature: float = 0.7
    max_tokens: int = 1000

    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True

    def __init__(self, eliza_provider: ElizaProvider, **kwargs):
        """Initialize wrapper with Eliza provider"""
        super().__init__(eliza_provider=eliza_provider, **kwargs)

    @property
    def _llm_type(self) -> str:
        """Return type of LLM"""
        return "eliza"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call Eliza provider synchronously

        Args:
            prompt: Input prompt
            stop: Stop sequences
            run_manager: Callback manager
            **kwargs: Additional arguments

        Returns:
            Generated text response
        """
        # Run async method in sync context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is running, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._acall_async(prompt, stop, **kwargs))
                return future.result()
        else:
            return loop.run_until_complete(self._acall_async(prompt, stop, **kwargs))

    async def _acall_async(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Async call to Eliza provider"""
        messages = [{"role": "user", "content": prompt}]

        response = await self.eliza_provider.chat_completion(
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stop=stop,
            **kwargs
        )

        return response.get("response", "")

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async version of _call"""
        return await self._acall_async(prompt, stop, **kwargs)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get identifying parameters"""
        return {
            "provider": "eliza",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }


class MultiProviderLangChainWrapper(LLM):
    """
    LangChain wrapper that supports multiple LLM providers
    with automatic fallback
    """

    primary_provider: Any  # Can be any provider
    fallback_providers: List[Any] = []
    provider_name: str = "multi"
    temperature: float = 0.7
    max_tokens: int = 1000

    class Config:
        """Pydantic configuration"""
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        """Return type of LLM"""
        return self.provider_name

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call with fallback support"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._acall_with_fallback(prompt, stop, **kwargs))
                return future.result()
        else:
            return loop.run_until_complete(self._acall_with_fallback(prompt, stop, **kwargs))

    async def _acall_with_fallback(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Try primary provider, fallback to others on failure"""
        messages = [{"role": "user", "content": prompt}]

        # Try primary provider
        try:
            response = await self.primary_provider.chat_completion(
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                stop=stop,
                **kwargs
            )
            return response.get("response", "")
        except Exception as e:
            print(f"Primary provider failed: {e}")

            # Try fallback providers
            for fallback in self.fallback_providers:
                try:
                    response = await fallback.chat_completion(
                        messages=messages,
                        temperature=kwargs.get("temperature", self.temperature),
                        max_tokens=kwargs.get("max_tokens", self.max_tokens),
                        stop=stop,
                        **kwargs
                    )
                    return response.get("response", "")
                except Exception as fallback_error:
                    print(f"Fallback provider failed: {fallback_error}")
                    continue

            # All providers failed
            raise Exception("All LLM providers failed")

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Async version of _call"""
        return await self._acall_with_fallback(prompt, stop, **kwargs)

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get identifying parameters"""
        return {
            "provider": self.provider_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "has_fallback": len(self.fallback_providers) > 0
        }


def create_langchain_llm(provider_type: str, provider_instance: Any) -> LLM:
    """
    Factory function to create appropriate LangChain wrapper

    Args:
        provider_type: Type of provider (eliza, openai, anthropic, etc.)
        provider_instance: Instance of the provider

    Returns:
        LangChain LLM wrapper
    """
    if provider_type.lower() == "eliza":
        return ElizaLangChainWrapper(eliza_provider=provider_instance)
    elif provider_type.lower() in ["openai", "anthropic", "litellm"]:
        return MultiProviderLangChainWrapper(
            primary_provider=provider_instance,
            provider_name=provider_type
        )
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def create_multi_provider_llm(
    primary_provider: Any,
    fallback_providers: List[Any] = None
) -> LLM:
    """
    Create multi-provider LLM with fallback support

    Args:
        primary_provider: Primary LLM provider
        fallback_providers: List of fallback providers

    Returns:
        Multi-provider LangChain wrapper
    """
    return MultiProviderLangChainWrapper(
        primary_provider=primary_provider,
        fallback_providers=fallback_providers or [],
        provider_name="multi"
    )
