"""
Configuration loader and manager for the chatbot system.
Implements hot-reload capability with file watcher.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError, ConfigDict
from pydantic_settings import BaseSettings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database connection configuration."""
    host: str
    port: int
    database: str = Field(alias="db")
    user: str
    password: str
    pool_size: int = 20
    pool_min: int = 5
    pool_max: int = 30


class ElizaConfig(BaseModel):
    """Eliza LLM gateway configuration."""
    cert_path: str
    private_key_path: str
    environment: str = "QA"
    default_model: str = "llama-3.3"
    timeout: int = 30
    retry_attempts: int = 3


class RedisConfig(BaseModel):
    """Redis cache configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl: int = 3600


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000"]
    rate_limit: int = 100
    timeout: int = 30


class AppSettings(BaseSettings):
    """Application settings from environment variables."""

    # Application
    app_name: str = "Financial Case Management Chatbot"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # Security
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # LangGraph Multi-Agent Orchestration
    use_langgraph: bool = Field(False, env="USE_LANGGRAPH")
    langgraph_enable_parallel: bool = Field(True, env="LANGGRAPH_ENABLE_PARALLEL")
    langgraph_enable_caching: bool = Field(True, env="LANGGRAPH_ENABLE_CACHING")
    langgraph_max_iterations: int = Field(10, env="LANGGRAPH_MAX_ITERATIONS")
    langgraph_timeout: int = Field(300, env="LANGGRAPH_TIMEOUT")
    langgraph_log_level: str = Field("INFO", env="LANGGRAPH_LOG_LEVEL")

    # LLM Streaming Configuration
    enable_llm_streaming: bool = Field(True, env="ENABLE_LLM_STREAMING")
    llm_streaming_chunk_size: int = Field(5, env="LLM_STREAMING_CHUNK_SIZE")
    llm_streaming_delay_ms: int = Field(50, env="LLM_STREAMING_DELAY_MS")

    # Visualization Configuration
    enable_visualizations: bool = Field(True, env="ENABLE_VISUALIZATIONS")
    visualization_min_data_points: int = Field(2, env="VISUALIZATION_MIN_DATA_POINTS")
    visualization_max_data_points: int = Field(100, env="VISUALIZATION_MAX_DATA_POINTS")
    visualization_delay_ms: int = Field(100, env="VISUALIZATION_DELAY_MS")
    visualization_default_colors: str = Field(
        '["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1"]',
        env="VISUALIZATION_DEFAULT_COLORS"
    )

    # Per-Agent Model Configuration
    execution_planner_model: Optional[str] = Field(None, env="EXECUTION_PLANNER_MODEL")
    tool_selector_model: Optional[str] = Field(None, env="TOOL_SELECTOR_MODEL")
    response_formatter_model: Optional[str] = Field(None, env="RESPONSE_FORMATTER_MODEL")
    consolidator_model: Optional[str] = Field(None, env="CONSOLIDATOR_MODEL")

    def get_model_for_agent(self, agent_type: str) -> str:
        """
        Get model for specific agent type, fallback to default ANTHROPIC_MODEL.

        Args:
            agent_type: One of: execution_planner, tool_selector, response_formatter, consolidator

        Returns:
            Model name to use for this agent
        """
        model_map = {
            "execution_planner": self.execution_planner_model,
            "tool_selector": self.tool_selector_model,
            "response_formatter": self.response_formatter_model,
            "consolidator": self.consolidator_model,
        }
        # Return agent-specific model or fallback to default
        agent_model = model_map.get(agent_type)
        if agent_model:
            return agent_model

        # Fallback to ANTHROPIC_MODEL or default
        return getattr(self, 'anthropic_model', 'claude-3-5-haiku-20241022')

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="allow"  # Allow extra fields from .env
    )


class ConfigLoader:
    """
    Configuration loader with hot-reload capability.
    Loads YAML configurations and merges with environment variables.
    """

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_cache: Dict[str, Any] = {}
        self.observer = None
        self.settings = AppSettings()

        # Load initial configuration
        self.reload_config()

    def load_config(self, path: str) -> Dict[str, Any]:
        """
        Load YAML configuration file.

        Args:
            path: Path to the YAML file

        Returns:
            Dictionary containing configuration data
        """
        try:
            file_path = self.config_dir / path if not Path(path).is_absolute() else Path(path)

            with open(file_path, 'r') as file:
                config = yaml.safe_load(file)

            # Replace environment variables
            config = self._replace_env_vars(config)

            logger.info(f"Loaded configuration from {file_path}")
            return config

        except FileNotFoundError:
            logger.error(f"Configuration file not found: {path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {path}: {e}")
            return {}

    def _replace_env_vars(self, config: Any) -> Any:
        """
        Recursively replace environment variables in configuration.
        Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            var_expr = config[2:-1]
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                return os.getenv(var_name, default)
            else:
                return os.getenv(var_expr, config)
        return config

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate configuration against Pydantic models.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Validate different sections
            if "database" in config:
                if "postgresql" in config["database"]:
                    DatabaseConfig(**config["database"]["postgresql"])
                if "oracle" in config["database"]:
                    DatabaseConfig(**config["database"]["oracle"])

            if "eliza" in config:
                ElizaConfig(**config["eliza"])

            if "redis" in config:
                RedisConfig(**config["redis"])

            if "api" in config:
                APIConfig(**config["api"])

            return True

        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.
        Later configs override earlier ones.

        Args:
            *configs: Configuration dictionaries to merge

        Returns:
            Merged configuration dictionary
        """
        result = {}

        for config in configs:
            self._deep_merge(result, config)

        return result

    def _deep_merge(self, target: Dict, source: Dict) -> Dict:
        """Deep merge source into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
        return target

    def get_environment_config(self) -> Dict[str, Any]:
        """
        Load environment-specific configuration.

        Returns:
            Environment-specific configuration
        """
        env = self.settings.environment
        env_config_file = f"config.{env}.yaml"

        # Load base config
        base_config = self.load_config("config.yaml")

        # Load environment-specific config
        env_config = self.load_config(env_config_file)

        # Merge configs (env-specific overrides base)
        merged = self.merge_configs(base_config, env_config)

        # Add settings from environment variables
        merged["app"] = {
            "name": self.settings.app_name,
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "debug": self.settings.debug
        }

        return merged

    def reload_config(self):
        """Reload all configurations."""
        logger.info("Reloading configuration...")
        self.config_cache = self.get_environment_config()

        # Validate the merged configuration
        if not self.validate_config(self.config_cache):
            logger.warning("Configuration validation failed, using previous config")

    def start_watching(self):
        """Start watching configuration files for changes."""
        if self.observer is not None:
            return

        event_handler = ConfigFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.config_dir), recursive=False)
        self.observer.start()
        logger.info(f"Started watching configuration files in {self.config_dir}")

    def stop_watching(self):
        """Stop watching configuration files."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped watching configuration files")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.
        Example: get("database.postgresql.host")
        """
        keys = key.split(".")
        value = self.config_cache

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_eliza_config(self) -> ElizaConfig:
        """Get validated Eliza configuration."""
        return ElizaConfig(**self.config_cache.get("eliza", {}))

    def get_database_config(self, db_type: str) -> DatabaseConfig:
        """Get validated database configuration."""
        return DatabaseConfig(**self.config_cache.get("database", {}).get(db_type, {}))

    def get_redis_config(self) -> RedisConfig:
        """Get validated Redis configuration."""
        return RedisConfig(**self.config_cache.get("redis", {}))

    def get_api_config(self) -> APIConfig:
        """Get validated API configuration."""
        return APIConfig(**self.config_cache.get("api", {}))


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for configuration file changes."""

    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.yaml'):
            logger.info(f"Configuration file changed: {event.src_path}")
            self.config_loader.reload_config()


# Global config instance
config_loader = ConfigLoader()

# Convenience functions
def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value."""
    return config_loader.get(key, default)

def get_settings() -> AppSettings:
    """Get application settings."""
    return config_loader.settings