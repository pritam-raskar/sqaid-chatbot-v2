"""
Tool Initializer - Dynamically loads and registers all tools from configuration

This module reads endpoint configurations and database schemas to automatically
create and register tools that the LangChain agent can use.
"""
import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.tools.custom_tools import (
    ConfiguredRESTTool,
    ConfiguredSOAPTool,
    ConfiguredDatabaseTool
)
from app.config.endpoint_loader import get_endpoint_loader, EndpointDefinition
from app.config.soap_endpoint_loader import get_soap_endpoint_loader, SOAPEndpointDefinition
from app.config.database_schema_loader import get_database_schema_loader, TableDefinition
from app.data_access.adapters.rest_adapter import RESTAdapter
from app.data.soap_adapter import SOAPAdapter

logger = logging.getLogger(__name__)


class ToolInitializer:
    """
    Initializes and registers all available tools from configuration
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        embeddings: Optional[Embeddings] = None,
        config_path: Optional[str] = None
    ):
        """
        Initialize tool initializer

        Args:
            tool_registry: Registry to register tools in
            embeddings: Optional embeddings model for semantic search
            config_path: Optional path to config directory (defaults to /config)
        """
        self.tool_registry = tool_registry
        self.embeddings = embeddings

        # Use generic config path if not specified
        if config_path is None:
            # Try to find config directory relative to project root
            backend_path = Path(__file__).parent.parent.parent
            config_path = backend_path / "config"
            if not config_path.exists():
                # Fallback to app/config
                config_path = backend_path / "app" / "config"

        self.config_path = Path(config_path)
        logger.info(f"Tool initializer using config path: {self.config_path}")

    async def initialize_all_tools(self) -> None:
        """
        Initialize and register all tools from configuration

        This includes:
        1. REST API endpoints from api_endpoints.yaml
        2. SOAP endpoints (if configured)
        3. Database tools (if configured)
        """
        logger.info("Initializing all tools...")

        # Initialize REST API tools from configuration
        await self._initialize_rest_api_tools()

        # Initialize SOAP API tools (if configured)
        await self._initialize_soap_api_tools()

        # Initialize database tools (if configured)
        await self._initialize_database_tools()

        # Log summary
        all_tools = self.tool_registry.list_tools()
        logger.info(f"Successfully initialized {len(all_tools)} tools")
        for tool_info in all_tools:
            logger.info(f"  - {tool_info['name']} ({tool_info['data_source']})")

    async def _initialize_rest_api_tools(self) -> None:
        """
        Load REST API endpoints from api_endpoints.yaml and register as tools
        """
        try:
            # Load endpoint configuration
            endpoint_loader = get_endpoint_loader()
            endpoints = endpoint_loader.get_all_endpoints()

            if not endpoints:
                logger.warning("No REST API endpoints found in configuration")
                return

            logger.info(f"Loading {len(endpoints)} REST API endpoints...")

            # Get base configuration
            auth_headers = endpoint_loader.build_headers()
            base_url = os.getenv(
                endpoint_loader.config.base_url_env_var,
                endpoint_loader.config.default_base_url
            )

            # Create REST adapter with proper config
            rest_adapter = RESTAdapter(config={
                'base_url': base_url,
                'headers': auth_headers,
                'config': {
                    'base_url': base_url,
                    'timeout': 30,
                    'retry_attempts': 3
                }
            })

            # Register each endpoint as a separate tool
            for endpoint_def in endpoints:
                await self._register_rest_endpoint_tool(
                    endpoint_def,
                    rest_adapter,
                    endpoint_loader
                )

        except Exception as e:
            logger.error(f"Failed to initialize REST API tools: {e}", exc_info=True)

    async def _register_rest_endpoint_tool(
        self,
        endpoint_def: EndpointDefinition,
        rest_adapter: RESTAdapter,
        endpoint_loader
    ) -> None:
        """
        Register a single REST endpoint as a tool

        Args:
            endpoint_def: Endpoint definition from configuration
            rest_adapter: REST API adapter instance
            endpoint_loader: Endpoint loader instance
        """
        try:
            # Extract endpoint path from full URL
            from urllib.parse import urlparse
            parsed_url = urlparse(endpoint_def.url)
            endpoint_path = parsed_url.path if parsed_url.path else endpoint_def.url

            # Create configured REST tool for this endpoint
            tool = ConfiguredRESTTool(
                name=f"rest_{endpoint_def.name}",
                description=endpoint_def.description,
                endpoint_url=endpoint_path,
                http_method=endpoint_def.method,
                api_adapter=rest_adapter,
                base_url=endpoint_loader.config.default_base_url
            )

            # Extract keywords from endpoint name and description
            keywords = self._extract_keywords(endpoint_def.name, endpoint_def.description)

            # Extract capabilities from description
            capabilities = self._extract_capabilities(endpoint_def.description, endpoint_def.method)

            # Register in tool registry
            await self.tool_registry.register_tool(
                tool=tool,
                capabilities=capabilities,
                keywords=keywords,
                data_source="rest_api",
                priority=7  # REST APIs get higher priority
            )

            logger.info(f"Registered REST endpoint tool: {endpoint_def.name}")

        except Exception as e:
            logger.error(f"Failed to register REST endpoint {endpoint_def.name}: {e}")

    async def _initialize_soap_api_tools(self) -> None:
        """
        Load SOAP endpoints from soap_endpoints.yaml and register as tools
        """
        try:
            # Load SOAP endpoint configuration
            soap_loader = get_soap_endpoint_loader()
            soap_endpoints = soap_loader.get_all_endpoints()

            if not soap_endpoints:
                logger.info("No SOAP endpoints configured")
                return

            logger.info(f"Loading {len(soap_endpoints)} SOAP endpoints...")

            # Get authentication config
            auth_config = soap_loader.get_auth_config()

            # Group endpoints by WSDL URL (reuse adapter)
            adapters_by_wsdl = {}

            # Register each endpoint as a separate tool
            for soap_def in soap_endpoints:
                await self._register_soap_endpoint_tool(
                    soap_def,
                    auth_config,
                    adapters_by_wsdl
                )

            logger.info(f"Registered {len(soap_endpoints)} SOAP endpoint tools")

        except Exception as e:
            logger.error(f"Failed to initialize SOAP API tools: {e}", exc_info=True)

    async def _register_soap_endpoint_tool(
        self,
        soap_def: SOAPEndpointDefinition,
        auth_config: Dict[str, Any],
        adapters_by_wsdl: Dict[str, SOAPAdapter]
    ) -> None:
        """
        Register a single SOAP endpoint as a tool

        Args:
            soap_def: SOAP endpoint definition from configuration
            auth_config: Authentication configuration
            adapters_by_wsdl: Cache of SOAP adapters by WSDL URL
        """
        try:
            # Get or create SOAP adapter for this WSDL
            wsdl_url = soap_def.wsdl_url

            if wsdl_url not in adapters_by_wsdl:
                soap_adapter = SOAPAdapter(
                    wsdl_url=wsdl_url,
                    username=auth_config.get('username'),
                    password=auth_config.get('password')
                )
                await soap_adapter.connect()
                adapters_by_wsdl[wsdl_url] = soap_adapter
            else:
                soap_adapter = adapters_by_wsdl[wsdl_url]

            # Create configured SOAP tool for this operation
            tool = ConfiguredSOAPTool(
                name=f"soap_{soap_def.name}",
                description=soap_def.description,
                operation_name=soap_def.operation,
                soap_adapter=soap_adapter,
                wsdl_url=wsdl_url
            )

            # Extract keywords from endpoint name and description
            keywords = self._extract_keywords(soap_def.name, soap_def.description)

            # Extract capabilities from description
            capabilities = self._extract_capabilities(soap_def.description, "SOAP")

            # Register in tool registry
            await self.tool_registry.register_tool(
                tool=tool,
                capabilities=capabilities,
                keywords=keywords,
                data_source="soap_api",
                priority=6
            )

            logger.info(f"Registered SOAP endpoint tool: {soap_def.name} ({soap_def.operation})")

        except Exception as e:
            logger.error(f"Failed to register SOAP endpoint {soap_def.name}: {e}")

    async def _initialize_database_tools(self) -> None:
        """
        Initialize database tools with semantic descriptions from configuration
        """
        try:
            # Load database schema configuration
            schema_loader = get_database_schema_loader()

            # Initialize tools for each configured database
            for db_type, db_config in schema_loader.get_all_databases().items():
                # Check if database is actually configured in environment
                if schema_loader.is_database_configured(db_type):
                    await self._initialize_database_for_type(db_type, schema_loader)
                else:
                    logger.info(f"{db_type} database not configured in environment, skipping")

        except Exception as e:
            logger.error(f"Failed to initialize database tools: {e}", exc_info=True)

    async def _initialize_database_for_type(
        self,
        db_type: str,
        schema_loader
    ) -> None:
        """
        Initialize tools for a specific database type

        Args:
            db_type: Database type (oracle, postgresql)
            schema_loader: DatabaseSchemaLoader instance
        """
        try:
            db_config = schema_loader.get_database_config(db_type)
            if not db_config:
                return

            logger.info(f"Initializing {db_type} database tools...")

            # Get connection config from environment
            conn_config = schema_loader.build_connection_config(db_type)

            # Register one tool per table (with semantic description)
            for table_def in db_config.tables:
                await self._register_database_table_tool(
                    db_type=db_type,
                    table_def=table_def,
                    conn_config=conn_config
                )

            logger.info(f"Registered {len(db_config.tables)} {db_type} table tools")

        except Exception as e:
            logger.error(f"Failed to initialize {db_type} tools: {e}", exc_info=True)

    async def _register_database_table_tool(
        self,
        db_type: str,
        table_def: TableDefinition,
        conn_config: Dict[str, Any]
    ) -> None:
        """
        Register a single database table as a tool

        Args:
            db_type: Database type
            table_def: Table definition from configuration
            conn_config: Database connection configuration
        """
        try:
            # Get database configuration to retrieve default schema
            from app.config.database_schema_loader import get_database_schema_loader
            schema_loader = get_database_schema_loader()
            db_config_obj = schema_loader.get_database_config(db_type)
            default_schema = db_config_obj.default_schema if db_config_obj else None

            # Get schema-qualified table name (e.g., info_alert.cm_alerts)
            qualified_table_name = table_def.get_qualified_name(default_schema)

            # Create database adapter based on type
            db_adapter = None
            if db_type == "postgresql":
                from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter
                # PostgreSQLAdapter expects nested config with database.postgresql structure
                # But also works with direct config
                db_adapter = PostgreSQLAdapter(config={
                    'database': {
                        'postgresql': {
                            'host': conn_config.get('host'),
                            'port': conn_config.get('port', 5432),
                            'db': conn_config.get('database'),
                            'user': conn_config.get('user'),
                            'password': conn_config.get('password')
                        }
                    }
                })
            elif db_type == "oracle":
                from app.data_access.adapters.oracle_adapter import OracleAdapter
                # OracleAdapter expects user, password, dsn as direct parameters
                dsn = f"{conn_config.get('host')}:{conn_config.get('port', 1521)}/{conn_config.get('service_name')}"
                db_adapter = OracleAdapter(
                    user=conn_config.get('user'),
                    password=conn_config.get('password'),
                    dsn=dsn
                )
            else:
                logger.warning(f"Unsupported database type: {db_type}")
                return

            # Build enhanced description with column information
            enhanced_description = self._build_enhanced_description(table_def)

            # Create configured database tool for this table
            tool = ConfiguredDatabaseTool(
                name=f"query_{db_type}_{table_def.name}",
                description=enhanced_description,
                table_name=qualified_table_name,
                db_adapter=db_adapter
            )

            # Use configured keywords
            keywords = table_def.keywords

            # Extract capabilities from description
            capabilities = self._extract_capabilities(table_def.description, "DATABASE")
            capabilities.extend(["query_database", "filter_data"])

            # Register in tool registry
            await self.tool_registry.register_tool(
                tool=tool,
                capabilities=capabilities,
                keywords=keywords,
                data_source=f"{db_type}_db",
                priority=6
            )

            logger.info(f"Registered DB table tool: {qualified_table_name}")

        except Exception as e:
            logger.error(f"Failed to register {db_type}.{table_def.name}: {e}")

    def _extract_keywords(self, name: str, description: str) -> List[str]:
        """
        Extract keywords from endpoint name and description

        Args:
            name: Endpoint name
            description: Endpoint description

        Returns:
            List of keywords
        """
        keywords = set()

        # Add words from name (split on underscore)
        keywords.update(name.lower().replace("_", " ").split())

        # Add important words from description (simple extraction)
        important_words = [
            "case", "cases", "ticket", "tickets", "bug", "bugs", "issue", "issues",
            "user", "users", "customer", "customers",
            "search", "find", "get", "list", "create", "update", "delete",
            "status", "priority", "assigned", "assignee",
            "comment", "comments", "note", "notes",
            "statistic", "statistics", "metric", "metrics", "report", "reports",
            "alert", "alerts", "position", "positions", "location", "locations"
        ]

        desc_lower = description.lower()
        for word in important_words:
            if word in desc_lower:
                keywords.add(word)

        return list(keywords)


    def _extract_capabilities(self, description: str, method: str) -> List[str]:
        """
        Extract capabilities from endpoint description and HTTP method

        Args:
            description: Endpoint description
            method: HTTP method (GET, POST, PUT, DELETE)

        Returns:
            List of capabilities
        """
        capabilities = set()

        desc_lower = description.lower()

        # Map HTTP methods to capabilities
        method_capabilities = {
            "GET": ["query", "read", "retrieve"],
            "POST": ["create", "submit", "add"],
            "PUT": ["update", "modify", "edit"],
            "DELETE": ["delete", "remove"]
        }

        capabilities.update(method_capabilities.get(method.upper(), []))

        # Add capabilities based on keywords in description
        if any(word in desc_lower for word in ["search", "find", "filter", "query"]):
            capabilities.add("search")
            capabilities.add("filter_data")

        if any(word in desc_lower for word in ["list", "all", "get"]):
            capabilities.add("list")
            capabilities.add("retrieve_multiple")

        if any(word in desc_lower for word in ["detail", "specific", "by id"]):
            capabilities.add("retrieve_single")

        if any(word in desc_lower for word in ["statistic", "metric", "count", "aggregate"]):
            capabilities.add("aggregate_data")
            capabilities.add("statistics")

        if any(word in desc_lower for word in ["comment", "note"]):
            capabilities.add("comments")

        return list(capabilities)

    def _build_enhanced_description(self, table_def: TableDefinition) -> str:
        """
        Build enhanced tool description that includes column information

        Args:
            table_def: Table definition from configuration

        Returns:
            Enhanced description with column information
        """
        # Start with the base semantic description
        description = table_def.description

        # Add column information if searchable_columns are defined
        if table_def.searchable_columns:
            description += f"\n\nAvailable columns: {', '.join(table_def.searchable_columns)}"

        # Add column metadata details if available
        if hasattr(table_def, 'column_metadata') and table_def.column_metadata:
            description += "\n\nColumn details:"
            for col_name, col_info in table_def.column_metadata.items():
                col_type = col_info.get('type', 'unknown')
                col_desc = col_info.get('description', '')

                # Add enum values if available
                if col_type == 'enum' and 'possible_values' in col_info:
                    values = ', '.join(col_info['possible_values'])
                    description += f"\n- {col_name} ({col_type}: {values}): {col_desc}"
                else:
                    description += f"\n- {col_name} ({col_type}): {col_desc}"

        return description


# Global instance
_tool_initializer: Optional[ToolInitializer] = None


async def initialize_tools(
    tool_registry: ToolRegistry,
    embeddings: Optional[Embeddings] = None,
    config_path: Optional[str] = None
) -> ToolInitializer:
    """
    Initialize all tools and register them in the tool registry

    Args:
        tool_registry: Tool registry instance
        embeddings: Optional embeddings model
        config_path: Optional config directory path

    Returns:
        ToolInitializer instance
    """
    global _tool_initializer

    if _tool_initializer is None:
        _tool_initializer = ToolInitializer(
            tool_registry=tool_registry,
            embeddings=embeddings,
            config_path=config_path
        )
        await _tool_initializer.initialize_all_tools()

    return _tool_initializer


def get_tool_initializer() -> Optional[ToolInitializer]:
    """Get global tool initializer instance"""
    return _tool_initializer
