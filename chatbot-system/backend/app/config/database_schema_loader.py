"""
Database Schema Configuration Loader

Loads and parses database schema definitions from YAML configuration files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict


class JoinDefinition(BaseModel):
    """Model for table join definition"""
    model_config = ConfigDict(populate_by_name=True)

    table: str
    table_schema: Optional[str] = Field(None, alias='schema')  # Schema name for the joined table
    join_on: str  # Join condition (renamed from 'on' to avoid YAML reserved keyword)
    description: str


class TableDefinition(BaseModel):
    """Model for database table definition"""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    table_schema: Optional[str] = Field(None, alias='schema')  # Schema/owner name (e.g., 'public', 'dbo', 'SECURITY')
    description: str
    keywords: List[str]
    primary_key: Optional[str] = None
    searchable_columns: List[str] = []
    common_joins: List[JoinDefinition] = []
    column_metadata: Optional[Dict[str, Dict[str, Any]]] = None  # Optional detailed column information

    def get_qualified_name(self, default_schema: Optional[str] = None) -> str:
        """
        Get fully qualified table name with schema.

        Args:
            default_schema: Default schema to use if table schema is not specified

        Returns:
            Qualified table name (e.g., 'public.users' or 'SECURITY.incidents')
        """
        schema = self.table_schema or default_schema
        if schema:
            return f"{schema}.{self.name}"
        return self.name


class DatabaseConfig(BaseModel):
    """Configuration for a single database"""
    connection_env_vars: Dict[str, str]
    default_schema: Optional[str] = None  # Default schema for this database
    tables: Optional[List[TableDefinition]] = None  # Optional tables list

    def __init__(self, **data):
        # Convert None to empty list for tables
        if data.get('tables') is None:
            data['tables'] = []
        super().__init__(**data)


class DatabaseSchemaConfig(BaseModel):
    """Complete database schema configuration"""
    databases: Dict[str, DatabaseConfig]
    query_timeout: int = 30
    max_results_default: int = 100
    enable_query_logging: bool = True


class DatabaseSchemaLoader:
    """Loads and manages database schema configurations"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize database schema loader

        Args:
            config_path: Path to YAML config file. If None, uses default location.
        """
        if config_path is None:
            # Try multiple locations
            backend_path = Path(__file__).parent.parent.parent
            possible_paths = [
                backend_path / "config" / "database_schemas.yaml",
                Path(__file__).parent / "database_schemas.yaml",
            ]

            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break

            if config_path is None:
                config_path = possible_paths[0]

        self.config_path = Path(config_path)
        self.config: Optional[DatabaseSchemaConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            # Return empty config if file doesn't exist
            self.config = DatabaseSchemaConfig(databases={})
            return

        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)

        if not raw_config:
            self.config = DatabaseSchemaConfig(databases={})
            return

        # Parse into Pydantic model
        self.config = DatabaseSchemaConfig(**raw_config)

    def get_database_config(self, db_type: str) -> Optional[DatabaseConfig]:
        """Get configuration for a specific database type"""
        if not self.config:
            return None

        return self.config.databases.get(db_type)

    def get_all_databases(self) -> Dict[str, DatabaseConfig]:
        """Get all database configurations"""
        if not self.config:
            return {}

        return self.config.databases

    def get_table_definition(self, db_type: str, table_name: str) -> Optional[TableDefinition]:
        """
        Get table definition by name

        Args:
            db_type: Database type (oracle, postgresql)
            table_name: Table name

        Returns:
            TableDefinition or None
        """
        db_config = self.get_database_config(db_type)
        if not db_config:
            return None

        for table in db_config.tables:
            if table.name.lower() == table_name.lower():
                return table

        return None

    def get_tables_by_keyword(self, db_type: str, keyword: str) -> List[TableDefinition]:
        """
        Find tables matching a keyword

        Args:
            db_type: Database type
            keyword: Keyword to search for

        Returns:
            List of matching table definitions
        """
        db_config = self.get_database_config(db_type)
        if not db_config:
            return []

        keyword_lower = keyword.lower()
        matching = []

        for table in db_config.tables:
            if keyword_lower in table.description.lower() or \
               keyword_lower in table.name.lower() or \
               any(keyword_lower in kw.lower() for kw in table.keywords):
                matching.append(table)

        return matching

    def build_connection_config(self, db_type: str) -> Dict[str, Any]:
        """
        Build connection configuration from environment variables

        Args:
            db_type: Database type

        Returns:
            Connection configuration dictionary
        """
        db_config = self.get_database_config(db_type)
        if not db_config:
            return {}

        conn_config = {}

        for key, env_var in db_config.connection_env_vars.items():
            value = os.getenv(env_var)
            if value:
                # Try to convert port to int
                if key == 'port' and value.isdigit():
                    conn_config[key] = int(value)
                else:
                    conn_config[key] = value

        return conn_config

    def is_database_configured(self, db_type: str) -> bool:
        """
        Check if a database type is configured and has connection info

        Args:
            db_type: Database type

        Returns:
            True if configured with valid connection info
        """
        conn_config = self.build_connection_config(db_type)

        # Check if required connection parameters are present
        if db_type == "oracle":
            required = ["host", "service_name", "user", "password"]
        elif db_type == "postgresql":
            required = ["host", "database", "user", "password"]
        else:
            return False

        return all(key in conn_config for key in required)


# Global instance
_database_schema_loader: Optional[DatabaseSchemaLoader] = None


def get_database_schema_loader() -> DatabaseSchemaLoader:
    """Get global database schema loader instance"""
    global _database_schema_loader

    if _database_schema_loader is None:
        _database_schema_loader = DatabaseSchemaLoader()

    return _database_schema_loader
