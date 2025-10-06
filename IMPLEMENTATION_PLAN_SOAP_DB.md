# Implementation Plan: SOAP & Database Configuration

## Analysis of Existing REST Implementation

### Current REST Endpoint Architecture (✅ Working)

#### 1. Configuration File Structure
**Location:** `backend/app/config/api_endpoints.yaml`

```yaml
endpoints:
  - name: "search_cases"                          # Tool name: rest_search_cases
    description: "Search for cases..."            # Used by LLM for semantic matching
    url: "${BASE_URL}/api/v1/cases/search"       # Runtime URL replacement
    method: "POST"                                 # HTTP method
    requires_auth: true                            # Auth flag
    parameters:                                    # Parameter definitions
      - name: "status"
        type: "string"
        description: "Case status..."
        required: false
        in: "body"                                 # Parameter location
```

#### 2. Configuration Loader
**Location:** `backend/app/config/endpoint_loader.py`

**Key Components:**
- `EndpointParameter` - Pydantic model for parameters
- `EndpointDefinition` - Pydantic model for endpoint
- `APIEndpointConfig` - Complete config with auth
- `EndpointLoader` class:
  - `_load_config()` - Reads YAML, validates with Pydantic
  - `_replace_env_vars()` - Replaces `${BASE_URL}` with env var
  - `build_headers()` - Builds auth headers from config
  - `get_all_endpoints()` - Returns all endpoint definitions

#### 3. Tool Initialization
**Location:** `backend/app/intelligence/tool_initializer.py`

**Process:**
1. Load endpoint config via `get_endpoint_loader()`
2. Create shared `RESTAPIAdapter` with auth headers
3. **For each endpoint:**
   - Create `RESTAPITool` with specific name/description
   - Wrap `_arun()` to inject configured URL/method
   - Extract keywords from description
   - Extract capabilities from HTTP method
   - Register in `ToolRegistry` with metadata

**Result:** Each REST endpoint = 1 LangChain tool with semantic description

---

## Implementation Plan: SOAP Endpoints

### Goal
Make SOAP configuration identical to REST - one tool per SOAP operation with semantic descriptions.

### Step 1: Create SOAP Configuration File

#### File: `backend/config/soap_endpoints.yaml`

```yaml
# SOAP Endpoint Configuration
# Define SOAP operations that the chatbot can access

soap_endpoints:
  - name: "get_customer_details"
    description: "Get customer information, profile, account details by customer ID, email, or phone number. Use this when user asks about customer data, account information, or customer lookup."
    wsdl_url: "${SOAP_WSDL_URL}"
    operation: "GetCustomerDetails"
    namespace: "http://example.com/customer/service"
    requires_auth: true
    parameters:
      - name: "customerId"
        type: "string"
        description: "Customer ID, email address, or phone number"
        required: true
      - name: "includeHistory"
        type: "boolean"
        description: "Include transaction and interaction history"
        required: false
        default: false
    response_format:
      type: "object"
      schema:
        customerId: "string"
        name: "string"
        email: "string"
        phone: "string"
        status: "string"

  - name: "process_payment"
    description: "Process payment transaction for customer invoices, orders, or bills. Use this when user wants to make payment, pay invoice, or process transaction."
    wsdl_url: "${SOAP_WSDL_URL}"
    operation: "ProcessPayment"
    namespace: "http://example.com/payment/service"
    requires_auth: true
    parameters:
      - name: "accountId"
        type: "string"
        description: "Account ID or invoice number"
        required: true
      - name: "amount"
        type: "decimal"
        description: "Payment amount in dollars"
        required: true
      - name: "paymentMethod"
        type: "string"
        description: "Payment method (credit_card, bank_transfer, check)"
        required: false
        default: "credit_card"

  - name: "validate_account"
    description: "Validate customer account status, check if account is active, suspended, or closed. Use this when verifying account status or checking account validity."
    wsdl_url: "${SOAP_WSDL_URL}"
    operation: "ValidateAccount"
    namespace: "http://example.com/validation/service"
    requires_auth: true
    parameters:
      - name: "accountNumber"
        type: "string"
        description: "Account number to validate"
        required: true

# Authentication Configuration
authentication:
  type: "basic"  # Options: basic, wsse, custom
  username_env_var: "SOAP_AUTH_USERNAME"
  password_env_var: "SOAP_AUTH_PASSWORD"

  # For WSSE security
  # type: "wsse"
  # username_env_var: "SOAP_USERNAME"
  # password_env_var: "SOAP_PASSWORD"
  # password_type: "PasswordText"  # or PasswordDigest

# Global SOAP Settings
default_wsdl_url: "${SOAP_WSDL_URL}"
timeout: 60  # SOAP calls can be slower
retry_attempts: 2
retry_delay: 2
soap_version: "1.1"  # or "1.2"
```

### Step 2: Create SOAP Endpoint Loader

#### File: `backend/app/config/soap_endpoint_loader.py`

```python
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
            possible_paths = [
                Path(__file__).parent.parent / "config" / "soap_endpoints.yaml",
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
```

### Step 3: Update Tool Initializer for SOAP

#### Modify: `backend/app/intelligence/tool_initializer.py`

**Add import:**
```python
from app.config.soap_endpoint_loader import get_soap_endpoint_loader, SOAPEndpointDefinition
```

**Replace `_initialize_soap_api_tools()` method:**

```python
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

        # Create a specialized SOAP tool for this operation
        tool = SOAPAPITool(
            name=f"soap_{soap_def.name}",
            description=soap_def.description,
            soap_adapter=soap_adapter,
            wsdl_url=wsdl_url
        )

        # Override the tool to use the specific operation
        original_arun = tool._arun
        specific_operation = soap_def.operation

        async def operation_specific_arun(
            action: str = "",
            parameters: str = "",
            run_manager=None
        ):
            """Wrapper that uses the configured operation"""
            # Use configured operation if not provided
            if not action:
                action = specific_operation

            return await original_arun(action, parameters, run_manager)

        tool._arun = operation_specific_arun

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
```

---

## Implementation Plan: Database Schemas

### Goal
Configure database tables with semantic descriptions, just like REST/SOAP endpoints.

### Step 1: Create Database Schema Configuration File

#### File: `backend/config/database_schemas.yaml`

```yaml
# Database Schema Configuration
# Define tables with semantic descriptions for LLM understanding

databases:
  # ========================================================================
  # ORACLE DATABASE
  # ========================================================================
  oracle:
    connection_env_vars:
      host: "ORACLE_HOST"
      port: "ORACLE_PORT"
      service_name: "ORACLE_SERVICE_NAME"
      user: "ORACLE_USER"
      password: "ORACLE_PASSWORD"

    tables:
      - name: "alert_positions"
        description: "Geographic positions and locations of security alerts, including latitude, longitude, and timestamp. Use this when user asks about alert locations, coordinates, positions, or where alerts occurred."
        keywords: ["position", "location", "coordinates", "latitude", "longitude", "alert location", "geography", "where"]
        primary_key: "alert_id"
        searchable_columns: ["alert_id", "lat", "lon", "timestamp"]
        common_joins:
          - table: "alerts"
            on: "alert_id"
            description: "Join with alerts table to get alert details"

      - name: "incidents"
        description: "Security incidents, events, breaches, violations, and security-related occurrences. Use this when user asks about security incidents, breaches, events, or violations."
        keywords: ["incident", "event", "breach", "security", "violation", "occurrence"]
        primary_key: "incident_id"
        searchable_columns: ["incident_id", "type", "severity", "status", "created_at"]

      - name: "audit_logs"
        description: "System audit logs, activity history, user actions, and system events for compliance and tracking. Use this when user asks about audit trail, user activity, system logs, or compliance records."
        keywords: ["audit", "log", "activity", "history", "tracking", "compliance"]
        primary_key: "log_id"
        searchable_columns: ["log_id", "user_id", "action", "timestamp"]

  # ========================================================================
  # POSTGRESQL DATABASE
  # ========================================================================
  postgresql:
    connection_env_vars:
      host: "POSTGRES_HOST"
      port: "POSTGRES_PORT"
      database: "POSTGRES_DB"
      user: "POSTGRES_USER"
      password: "POSTGRES_PASSWORD"

    tables:
      - name: "users"
        description: "User accounts, profiles, team members, employees, contacts, and system users. Use this when user asks about people, team members, employees, user information, or account details."
        keywords: ["user", "person", "employee", "member", "account", "profile", "team", "people"]
        primary_key: "user_id"
        searchable_columns: ["user_id", "email", "name", "department", "role"]
        common_joins:
          - table: "cases"
            on: "assigned_to = user_id"
            description: "Join with cases to get assigned cases"

      - name: "cases"
        description: "Support cases, tickets, issues, bug reports, customer requests, and help desk items. Use this when user asks about cases, tickets, issues, bugs, or support requests."
        keywords: ["case", "ticket", "issue", "bug", "support", "request", "problem"]
        primary_key: "case_id"
        searchable_columns: ["case_id", "status", "priority", "assigned_to", "created_at"]

      - name: "sessions"
        description: "User login sessions, authentication history, active sessions, and activity logs. Use this when user asks about sessions, logins, authentication, or who is currently logged in."
        keywords: ["session", "login", "authentication", "activity", "logged in", "active users"]
        primary_key: "session_id"
        searchable_columns: ["session_id", "user_id", "created_at", "expires_at"]

      - name: "notifications"
        description: "System notifications, alerts, messages, and user notifications. Use this when user asks about notifications, messages, alerts sent to users."
        keywords: ["notification", "message", "alert", "reminder", "notice"]
        primary_key: "notification_id"
        searchable_columns: ["notification_id", "user_id", "type", "status", "created_at"]

# Global Database Settings
query_timeout: 30
max_results_default: 100
enable_query_logging: true
```

### Step 2: Create Database Schema Loader

#### File: `backend/app/config/database_schema_loader.py`

```python
"""
Database Schema Configuration Loader

Loads and parses database schema definitions from YAML configuration files.
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from pydantic import BaseModel


class JoinDefinition(BaseModel):
    """Model for table join definition"""
    table: str
    on: str
    description: str


class TableDefinition(BaseModel):
    """Model for database table definition"""
    name: str
    description: str
    keywords: List[str]
    primary_key: Optional[str] = None
    searchable_columns: List[str] = []
    common_joins: List[JoinDefinition] = []


class DatabaseConfig(BaseModel):
    """Configuration for a single database"""
    connection_env_vars: Dict[str, str]
    tables: List[TableDefinition]


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
            possible_paths = [
                Path(__file__).parent.parent / "config" / "database_schemas.yaml",
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
```

### Step 3: Update Tool Initializer for Databases

#### Modify: `backend/app/intelligence/tool_initializer.py`

**Add import:**
```python
from app.config.database_schema_loader import get_database_schema_loader, TableDefinition
```

**Replace `_initialize_database_tools()` method:**

```python
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
        # Create database tool for specific table
        tool = DatabaseQueryTool(
            name=f"query_{db_type}_{table_def.name}",
            description=table_def.description,
            db_type=db_type,
            db_config=conn_config
        )

        # Override the tool to use the specific table
        original_arun = tool._arun
        specific_table = table_def.name

        async def table_specific_arun(
            table: str = "",
            columns: Optional[str] = None,
            filters: Optional[str] = None,
            limit: int = 100,
            order_by: Optional[str] = None,
            run_manager=None
        ):
            """Wrapper that uses the configured table"""
            # Use configured table if not provided
            if not table:
                table = specific_table

            return await original_arun(table, columns, filters, limit, order_by, run_manager)

        tool._arun = table_specific_arun

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

        logger.info(f"Registered DB table tool: {db_type}.{table_def.name}")

    except Exception as e:
        logger.error(f"Failed to register {db_type}.{table_def.name}: {e}")


# Remove old methods
# Delete: _get_postgres_config()
# Delete: _get_oracle_config()
# Delete: _register_database_tool()
```

---

## Summary: Complete Implementation Checklist

### Phase 1: SOAP Implementation

- [ ] Create `backend/config/soap_endpoints.yaml`
- [ ] Create `backend/app/config/soap_endpoint_loader.py`
- [ ] Update `backend/app/config/__init__.py` to export SOAP loader
- [ ] Modify `backend/app/intelligence/tool_initializer.py`:
  - [ ] Add import for `get_soap_endpoint_loader`
  - [ ] Replace `_initialize_soap_api_tools()` method
  - [ ] Add `_register_soap_endpoint_tool()` method
- [ ] Test SOAP endpoint loading
- [ ] Test SOAP tool registration

### Phase 2: Database Schema Implementation

- [ ] Create `backend/config/database_schemas.yaml`
- [ ] Create `backend/app/config/database_schema_loader.py`
- [ ] Update `backend/app/config/__init__.py` to export schema loader
- [ ] Modify `backend/app/intelligence/tool_initializer.py`:
  - [ ] Add import for `get_database_schema_loader`
  - [ ] Replace `_initialize_database_tools()` method
  - [ ] Add `_initialize_database_for_type()` method
  - [ ] Add `_register_database_table_tool()` method
  - [ ] Remove old database methods
- [ ] Test database schema loading
- [ ] Test database tool registration

### Phase 3: Testing & Validation

- [ ] Test REST endpoints still working
- [ ] Test SOAP endpoints registration
- [ ] Test database table registration
- [ ] Test multi-source query (REST + DB)
- [ ] Test multi-source query (SOAP + DB)
- [ ] Test multi-source query (REST + SOAP + DB)
- [ ] Validate tool descriptions are being used by LLM
- [ ] Performance testing with all tools loaded

---

## Expected Result

```
Tool Registry after implementation:

REST Tools (9 tools from api_endpoints.yaml):
  ✓ rest_search_cases
  ✓ rest_get_case_details
  ✓ rest_create_case
  ✓ rest_update_case
  ✓ rest_get_user_info
  ✓ rest_list_users
  ✓ rest_get_case_statistics
  ...

SOAP Tools (3 tools from soap_endpoints.yaml):
  ✓ soap_get_customer_details
  ✓ soap_process_payment
  ✓ soap_validate_account

Database Tools (7 tools from database_schemas.yaml):
  ✓ query_oracle_alert_positions
  ✓ query_oracle_incidents
  ✓ query_oracle_audit_logs
  ✓ query_postgresql_users
  ✓ query_postgresql_cases
  ✓ query_postgresql_sessions
  ✓ query_postgresql_notifications

Total: 19 tools, all with semantic descriptions
```

**LangChain agent can now intelligently choose from all 19 tools to answer any query!**
