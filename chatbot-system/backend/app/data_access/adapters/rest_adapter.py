"""
REST API Adapter for interfacing with RESTful services.
Includes retry logic, authentication, and response caching.
"""

import httpx
import logging
import json
from typing import Any, Dict, Optional, Union
from urllib.parse import urljoin
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log
)
import asyncio
from datetime import datetime, timedelta

from app.data_access.base_adapter import BaseDataAdapter

logger = logging.getLogger(__name__)


class RESTAdapter(BaseDataAdapter):
    """
    Adapter for REST API data sources.
    Handles authentication, retries, and caching.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize REST adapter with configuration.

        Args:
            config: Configuration containing:
                - base_url: Base URL for the API
                - auth_type: Authentication type (bearer, basic, api_key)
                - timeout: Request timeout in seconds
                - retry_attempts: Number of retry attempts
                - headers: Default headers
        """
        super().__init__(config)

        # Set base URL and auth
        self.base_url = config.get('config', {}).get('base_url', config.get('base_url'))
        self.auth_type = config.get('config', {}).get('auth_type', 'none')
        self.auth_credentials = None

        # Configure retry policy
        self.timeout = config.get('config', {}).get('timeout', 30)
        self.retry_attempts = config.get('config', {}).get('retry_attempts', 3)

        # Initialize connection pool
        self.client: Optional[httpx.AsyncClient] = None
        self.default_headers = config.get('headers', {})

        # Cache configuration
        self.cache_enabled = config.get('cache_enabled', False)
        self.cache_ttl = config.get('cache_ttl', 300)  # 5 minutes default
        self._cache: Dict[str, Dict[str, Any]] = {}

        logger.info(f"Initialized REST adapter for {self.base_url}")

    async def connect(self) -> None:
        """
        Establish connection to REST API.
        Creates HTTP client with connection pooling.
        """
        try:
            # Create async HTTP client with connection pooling
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self.default_headers,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                )
            )

            # Set up authentication
            await self._setup_authentication()

            # Test connection
            await self.health_check()

            self.is_connected = True
            logger.info(f"Connected to REST API at {self.base_url}")

        except Exception as e:
            logger.error(f"Failed to connect to REST API: {e}")
            raise

    async def disconnect(self) -> None:
        """Close HTTP client and cleanup resources."""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.is_connected = False
            logger.info(f"Disconnected from REST API at {self.base_url}")

    async def _setup_authentication(self):
        """Set up authentication based on configured type."""
        if self.auth_type == 'bearer':
            token = self.config.get('auth_token') or self.config.get('api_key')
            if token:
                self.client.headers['Authorization'] = f'Bearer {token}'

        elif self.auth_type == 'api_key':
            api_key = self.config.get('api_key')
            api_key_header = self.config.get('api_key_header', 'X-API-Key')
            if api_key:
                self.client.headers[api_key_header] = api_key

        elif self.auth_type == 'basic':
            username = self.config.get('username')
            password = self.config.get('password')
            if username and password:
                self.client.auth = httpx.BasicAuth(username, password)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before=before_log(logger, logging.WARNING),
        after=after_log(logger, logging.WARNING)
    )
    async def execute(self, endpoint: str, method: str = 'GET', **kwargs) -> Dict[str, Any]:
        """
        Execute HTTP request with retry logic.

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            **kwargs: Additional request parameters (params, json, data, headers)

        Returns:
            Response data as dictionary

        Steps:
        1. Build full URL
        2. Add authentication headers
        3. Make async HTTP request
        4. Handle status codes
        5. Parse JSON response
        6. Cache if configured
        """
        if not self.client:
            await self.connect()

        # Step 1: Build full URL
        url = endpoint if endpoint.startswith('http') else urljoin(str(self.base_url), endpoint)

        # Check cache for GET requests
        cache_key = f"{method}:{url}:{json.dumps(kwargs.get('params', {}))}"
        if method == 'GET' and self.cache_enabled:
            cached = self._get_from_cache(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key}")
                return cached

        try:
            # Step 2: Authentication headers are already set in client

            # Step 3: Make async HTTP request
            logger.debug(f"Making {method} request to {url}")
            response = await self.client.request(
                method=method,
                url=url,
                **kwargs
            )

            # Step 4: Handle status codes
            response.raise_for_status()

            # Step 5: Parse JSON response
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {'text': response.text}

            # Step 6: Cache if configured
            if method == 'GET' and self.cache_enabled:
                self._add_to_cache(cache_key, data)

            logger.debug(f"Request successful: {method} {url}")
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
            return {
                'error': True,
                'status_code': e.response.status_code,
                'message': e.response.text
            }
        except Exception as e:
            logger.error(f"Request failed for {url}: {e}")
            raise

    async def retry_with_backoff(self, func, *args, **kwargs):
        """
        Retry a function with exponential backoff.

        Args:
            func: Async function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        for attempt in range(self.retry_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    logger.error(f"Max retry attempts reached: {e}")
                    raise

                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

    async def health_check(self) -> bool:
        """
        Check if the REST API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try to access a health endpoint or the base URL
            health_endpoint = self.config.get('health_endpoint', '/')
            response = await self.execute(health_endpoint, 'GET')
            return not response.get('error', False)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def _add_to_cache(self, key: str, data: Any):
        """Add data to cache with TTL."""
        self._cache[key] = {
            'data': data,
            'expires_at': datetime.utcnow() + timedelta(seconds=self.cache_ttl)
        }

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if key in self._cache:
            cache_entry = self._cache[key]
            if datetime.utcnow() < cache_entry['expires_at']:
                return cache_entry['data']
            else:
                # Remove expired entry
                del self._cache[key]
        return None

    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        logger.info("Cache cleared")

    # Convenience methods for common HTTP verbs
    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform GET request."""
        return await self.execute(endpoint, 'GET', params=params)

    async def post(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform POST request."""
        return await self.execute(endpoint, 'POST', json=json_data)

    async def put(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform PUT request."""
        return await self.execute(endpoint, 'PUT', json=json_data)

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Perform DELETE request."""
        return await self.execute(endpoint, 'DELETE')

    async def patch(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Perform PATCH request."""
        return await self.execute(endpoint, 'PATCH', json=json_data)