"""
API Endpoint Configuration Loader

Loads and parses API endpoint definitions from YAML configuration files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field


class EndpointParameter(BaseModel):
    """Model for endpoint parameter definition"""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None
    in_: str = Field(default="body", alias="in")  # body, path, query, header


class EndpointDefinition(BaseModel):
    """Model for REST endpoint definition"""
    name: str
    description: str
    url: str
    method: str
    requires_auth: bool = True
    parameters: List[EndpointParameter] = []
    response_format: Optional[Dict[str, Any]] = None


class APIEndpointConfig(BaseModel):
    """Complete API configuration"""
    endpoints: List[EndpointDefinition]
    authentication: Dict[str, Any]
    base_url_env_var: str = "API_BASE_URL"
    default_base_url: str = "http://localhost:8000"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 1


class EndpointLoader:
    """Loads and manages API endpoint configurations"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize endpoint loader

        Args:
            config_path: Path to YAML config file. If None, uses default location.
        """
        if config_path is None:
            # Use generic /config directory (backend/config/api_endpoints.yaml)
            backend_path = Path(__file__).parent.parent.parent
            config_path = backend_path / "config" / "api_endpoints.yaml"

        self.config_path = Path(config_path)
        self.config: Optional[APIEndpointConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Endpoint config not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        # Replace environment variables in URLs
        self._replace_env_vars(raw_config)

        # Parse into Pydantic model
        self.config = APIEndpointConfig(**raw_config)

    def _replace_env_vars(self, config: Dict) -> None:
        """Replace ${VAR} patterns with environment variables"""
        base_url = os.getenv(
            config.get('base_url_env_var', 'API_BASE_URL'),
            config.get('default_base_url', 'http://localhost:8000')
        )

        # Replace ${BASE_URL} in all endpoint URLs
        for endpoint in config.get('endpoints', []):
            if 'url' in endpoint:
                endpoint['url'] = endpoint['url'].replace('${BASE_URL}', base_url)

    def get_endpoint(self, name: str) -> Optional[EndpointDefinition]:
        """Get endpoint definition by name"""
        if not self.config:
            return None

        for endpoint in self.config.endpoints:
            if endpoint.name == name:
                return endpoint

        return None

    def get_all_endpoints(self) -> List[EndpointDefinition]:
        """Get all endpoint definitions"""
        if not self.config:
            return []

        return self.config.endpoints

    def get_endpoints_by_description(self, query: str) -> List[EndpointDefinition]:
        """
        Find endpoints matching a description query

        Args:
            query: Search query to match against endpoint descriptions

        Returns:
            List of matching endpoint definitions
        """
        if not self.config:
            return []

        query_lower = query.lower()
        matching = []

        for endpoint in self.config.endpoints:
            if query_lower in endpoint.description.lower() or query_lower in endpoint.name.lower():
                matching.append(endpoint)

        return matching

    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration"""
        if not self.config:
            return {}

        auth_config = self.config.authentication.copy()

        # Load token from environment if specified
        if 'token_env_var' in auth_config:
            token = os.getenv(auth_config['token_env_var'])
            if token:
                auth_config['token'] = token

        return auth_config

    def build_headers(self) -> Dict[str, str]:
        """Build authentication headers from config"""
        auth_config = self.get_auth_config()
        headers = {}

        if auth_config.get('type') == 'bearer' and 'token' in auth_config:
            prefix = auth_config.get('token_prefix', 'Bearer')
            header_name = auth_config.get('header_name', 'Authorization')
            headers[header_name] = f"{prefix} {auth_config['token']}"
        elif auth_config.get('type') == 'api_key' and 'token' in auth_config:
            header_name = auth_config.get('header_name', 'X-API-Key')
            headers[header_name] = auth_config['token']

        return headers

    def format_endpoint_url(self, endpoint: EndpointDefinition, path_params: Dict[str, Any]) -> str:
        """
        Format endpoint URL with path parameters

        Args:
            endpoint: Endpoint definition
            path_params: Dictionary of path parameter values

        Returns:
            Formatted URL
        """
        url = endpoint.url

        # Replace {param} patterns with actual values
        for param_name, param_value in path_params.items():
            url = url.replace(f"{{{param_name}}}", str(param_value))

        return url

    def get_endpoint_for_intent(self, intent: str) -> Optional[EndpointDefinition]:
        """
        Get the best matching endpoint for a user intent

        Args:
            intent: User intent or query description

        Returns:
            Best matching endpoint or None
        """
        matches = self.get_endpoints_by_description(intent)

        if not matches:
            return None

        # Return first match (could be enhanced with semantic similarity)
        return matches[0]


# Global instance
_endpoint_loader: Optional[EndpointLoader] = None


def get_endpoint_loader() -> EndpointLoader:
    """Get global endpoint loader instance"""
    global _endpoint_loader

    if _endpoint_loader is None:
        _endpoint_loader = EndpointLoader()

    return _endpoint_loader
