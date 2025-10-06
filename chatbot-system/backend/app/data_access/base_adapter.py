"""
Base adapter interface for all data source adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseDataAdapter(ABC):
    """
    Abstract base class for data source adapters.
    All data adapters must implement this interface.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: Adapter-specific configuration
        """
        self.config = config
        self.is_connected = False
        self.capabilities = config.get('capabilities', [])
        self.semantic_descriptions = config.get('semantic_descriptions', [])

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the data source."""
        pass

    @abstractmethod
    async def execute(self, operation: str, **kwargs) -> Any:
        """
        Execute an operation on the data source.

        Args:
            operation: Operation to perform
            **kwargs: Operation-specific parameters

        Returns:
            Operation result
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the data source is healthy and accessible.

        Returns:
            True if healthy, False otherwise
        """
        pass

    def get_capabilities(self) -> List[str]:
        """Get list of capabilities this adapter supports."""
        return self.capabilities

    def get_semantic_descriptions(self) -> List[str]:
        """Get semantic descriptions of what this adapter can do."""
        return self.semantic_descriptions

    def matches_capability(self, required_capability: str) -> bool:
        """
        Check if this adapter supports a required capability.

        Args:
            required_capability: Capability to check

        Returns:
            True if supported, False otherwise
        """
        return required_capability.lower() in [cap.lower() for cap in self.capabilities]

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()