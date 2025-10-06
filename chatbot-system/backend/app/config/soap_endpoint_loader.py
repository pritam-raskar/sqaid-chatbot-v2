"""
SOAP Endpoint Configuration Loader

Loads and parses SOAP endpoint definitions from YAML configuration files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field


class SOAPParameter(BaseModel):
    """Model for SOAP parameter definition"""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class SOAPEndpointDefinition(BaseModel):
    """Model for SOAP endpoint definition"""
    name: str
    description: str
    wsdl_url: str
    operation: str
    namespace: Optional[str] = None
    requires_auth: bool = True
    parameters: List[SOAPParameter] = []
    response_format: Optional[Dict[str, Any]] = None


class SOAPEndpointConfig(BaseModel):
    """Complete SOAP configuration"""
    soap_endpoints: List[SOAPEndpointDefinition]
    authentication: Dict[str, Any]
    default_wsdl_url: str = ""
    timeout: int = 60
    retry_attempts: int = 2
    retry_delay: int = 2
    soap_version: str = "1.1"


class SOAPEndpointLoader:
    """Loads and manages SOAP endpoint configurations"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize SOAP endpoint loader

        Args:
            config_path: Path to YAML config file. If None, uses default location.
        """
        if config_path is None:
            # Try multiple locations
            backend_path = Path(__file__).parent.parent.parent
            possible_paths = [
                backend_path / "config" / "soap_endpoints.yaml",
                Path(__file__).parent / "soap_endpoints.yaml",
            ]

            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break

            if config_path is None:
                # Use first path as default (will be created)
                config_path = possible_paths[0]

        self.config_path = Path(config_path)
        self.config: Optional[SOAPEndpointConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            # Return empty config if file doesn't exist
            self.config = SOAPEndpointConfig(
                soap_endpoints=[],
                authentication={},
                default_wsdl_url=""
            )
            return

        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        if not raw_config:
            self.config = SOAPEndpointConfig(
                soap_endpoints=[],
                authentication={},
                default_wsdl_url=""
            )
            return

        # Replace environment variables
        self._replace_env_vars(raw_config)

        # Parse into Pydantic model
        self.config = SOAPEndpointConfig(**raw_config)

    def _replace_env_vars(self, config: Dict) -> None:
        """Replace ${VAR} patterns with environment variables"""
        wsdl_url = os.getenv('SOAP_WSDL_URL', '')

        # Replace ${SOAP_WSDL_URL} in all endpoint URLs
        for endpoint in config.get('soap_endpoints', []):
            if 'wsdl_url' in endpoint:
                endpoint['wsdl_url'] = endpoint['wsdl_url'].replace('${SOAP_WSDL_URL}', wsdl_url)

        # Replace in default WSDL URL
        if 'default_wsdl_url' in config:
            config['default_wsdl_url'] = config['default_wsdl_url'].replace('${SOAP_WSDL_URL}', wsdl_url)

    def get_endpoint(self, name: str) -> Optional[SOAPEndpointDefinition]:
        """Get endpoint definition by name"""
        if not self.config:
            return None

        for endpoint in self.config.soap_endpoints:
            if endpoint.name == name:
                return endpoint

        return None

    def get_all_endpoints(self) -> List[SOAPEndpointDefinition]:
        """Get all endpoint definitions"""
        if not self.config:
            return []

        return self.config.soap_endpoints

    def get_endpoints_by_description(self, query: str) -> List[SOAPEndpointDefinition]:
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

        for endpoint in self.config.soap_endpoints:
            if query_lower in endpoint.description.lower() or query_lower in endpoint.name.lower():
                matching.append(endpoint)

        return matching

    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration"""
        if not self.config:
            return {}

        auth_config = self.config.authentication.copy()

        # Load credentials from environment
        if 'username_env_var' in auth_config:
            username = os.getenv(auth_config['username_env_var'])
            if username:
                auth_config['username'] = username

        if 'password_env_var' in auth_config:
            password = os.getenv(auth_config['password_env_var'])
            if password:
                auth_config['password'] = password

        return auth_config

    def build_auth_headers(self) -> Dict[str, str]:
        """Build authentication headers/config for SOAP"""
        auth_config = self.get_auth_config()

        # SOAP auth is typically handled in SOAP envelope
        # Return config for SOAPAdapter to use
        return auth_config


# Global instance
_soap_endpoint_loader: Optional[SOAPEndpointLoader] = None


def get_soap_endpoint_loader() -> SOAPEndpointLoader:
    """Get global SOAP endpoint loader instance"""
    global _soap_endpoint_loader

    if _soap_endpoint_loader is None:
        _soap_endpoint_loader = SOAPEndpointLoader()

    return _soap_endpoint_loader
