"""
Metadata Manager - Loads and manages database schema metadata.

Provides access to column metadata including enum values, types, and constraints
from database_schemas.yaml configuration file. Used for intelligent value normalization
and case-insensitive matching.
"""
import logging
import yaml
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataManager:
    """
    Manages metadata for all data sources loaded from configuration.

    Responsibilities:
    - Load column metadata from database_schemas.yaml
    - Load parameter metadata from api_endpoints.yaml
    - Load parameter metadata from soap_endpoints.yaml
    - Provide enum possible values for columns/parameters
    - Fuzzy match user input to actual enum values (case-insensitive)
    - Cache metadata for performance
    """

    def __init__(self, config_path: str = None):
        """
        Initialize MetadataManager.

        Args:
            config_path: Path to config directory (defaults to backend/config/)
        """
        if config_path is None:
            # Default to config directory relative to this file
            backend_dir = Path(__file__).parent.parent.parent
            config_path = backend_dir / "config"

        self.config_dir = Path(config_path)
        self.metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}  # Database table metadata
        self.api_metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}  # REST API endpoint metadata
        self.soap_metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}  # SOAP operation metadata
        self._load_all_metadata()

    def _load_all_metadata(self):
        """Load metadata from all configuration files."""
        self._load_database_metadata()
        self._load_api_metadata()
        self._load_soap_metadata()

    def _load_database_metadata(self):
        """Load metadata from database_schemas.yaml file."""
        try:
            config_path = self.config_dir / "database_schemas.yaml"
            if not config_path.exists():
                logger.warning(f"Database metadata config file not found: {config_path}")
                return

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'databases' not in config:
                logger.warning("No databases section found in metadata config")
                return

            # Parse metadata for each database
            for db_type, db_config in config['databases'].items():
                if 'tables' not in db_config:
                    continue

                for table_config in db_config['tables']:
                    table_name = table_config.get('name')
                    schema = table_config.get('schema', 'public')
                    column_metadata = table_config.get('column_metadata', {})

                    if not table_name or not column_metadata:
                        continue

                    # Store metadata with schema-qualified table name
                    full_table_name = f"{schema}.{table_name}"

                    # Also store without schema for compatibility
                    self.metadata[table_name] = column_metadata
                    self.metadata[full_table_name] = column_metadata

            logger.info(f"✅ Loaded database metadata for {len(self.metadata)} tables")

        except Exception as e:
            logger.error(f"Failed to load database metadata from {config_path}: {e}", exc_info=True)

    def _load_api_metadata(self):
        """Load parameter metadata from api_endpoints.yaml file."""
        try:
            config_path = self.config_dir / "api_endpoints.yaml"
            if not config_path.exists():
                logger.warning(f"API metadata config file not found: {config_path}")
                return

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'endpoints' not in config:
                logger.warning("No endpoints section found in API metadata config")
                return

            # Parse parameter metadata for each endpoint
            for endpoint_config in config['endpoints']:
                endpoint_name = endpoint_config.get('name')
                param_metadata = endpoint_config.get('parameter_metadata', {})

                if not endpoint_name:
                    continue

                # Store metadata with endpoint name
                self.api_metadata[endpoint_name] = param_metadata

            logger.info(f"✅ Loaded API metadata for {len(self.api_metadata)} endpoints")

        except Exception as e:
            logger.error(f"Failed to load API metadata from {config_path}: {e}", exc_info=True)

    def _load_soap_metadata(self):
        """Load parameter metadata from soap_endpoints.yaml file."""
        try:
            config_path = self.config_dir / "soap_endpoints.yaml"
            if not config_path.exists():
                logger.warning(f"SOAP metadata config file not found: {config_path}")
                return

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config or 'soap_endpoints' not in config:
                logger.warning("No soap_endpoints section found in SOAP metadata config")
                return

            # Parse parameter metadata for each SOAP operation
            for endpoint_config in config['soap_endpoints']:
                operation_name = endpoint_config.get('name')
                param_metadata = endpoint_config.get('parameter_metadata', {})

                if not operation_name:
                    continue

                # Store metadata with operation name
                self.soap_metadata[operation_name] = param_metadata

            logger.info(f"✅ Loaded SOAP metadata for {len(self.soap_metadata)} operations")

        except Exception as e:
            logger.error(f"Failed to load SOAP metadata from {config_path}: {e}", exc_info=True)

    def get_column_metadata(self, table_name: str, column_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific column.

        Args:
            table_name: Table name (can be schema-qualified like "info_alert.cm_alerts")
            column_name: Column name

        Returns:
            Column metadata dict or None if not found
        """
        if table_name not in self.metadata:
            return None

        table_metadata = self.metadata[table_name]
        return table_metadata.get(column_name)

    def is_enum_column(self, table_name: str, column_name: str) -> bool:
        """
        Check if a column is an enum type.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            True if column is enum type, False otherwise
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta:
            return False

        return col_meta.get('type') == 'enum'

    def get_enum_values(self, table_name: str, column_name: str) -> Optional[List[str]]:
        """
        Get possible enum values for a column.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            List of possible enum values or None if not an enum column
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta or col_meta.get('type') != 'enum':
            return None

        return col_meta.get('possible_values', [])

    def normalize_enum_value(self, table_name: str, column_name: str, user_value: str) -> Optional[str]:
        """
        Normalize user input to match actual enum value (case-insensitive).

        Args:
            table_name: Table name
            column_name: Column name
            user_value: Value provided by user (any case)

        Returns:
            Actual enum value with correct case, or None if no match found

        Example:
            normalize_enum_value("cm_alerts", "status", "open") -> "Open"
            normalize_enum_value("cm_alerts", "status", "OPEN") -> "Open"
            normalize_enum_value("cm_alerts", "status", "OpEn") -> "Open"
        """
        enum_values = self.get_enum_values(table_name, column_name)
        if not enum_values:
            return None

        # Try exact match first (fast path)
        if user_value in enum_values:
            return user_value

        # Try case-insensitive match
        user_value_lower = user_value.lower()
        for enum_value in enum_values:
            if enum_value.lower() == user_value_lower:
                return enum_value

        # No match found
        return None

    def is_case_sensitive(self, table_name: str, column_name: str) -> bool:
        """
        Check if a column is case-sensitive.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            True if case-sensitive, False if case-insensitive (default for enums)
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta:
            return True  # Default to case-sensitive if no metadata

        # Enums are case-insensitive by default
        if col_meta.get('type') == 'enum':
            return col_meta.get('case_sensitive', False)

        return True

    def get_column_type(self, table_name: str, column_name: str) -> Optional[str]:
        """
        Get the data type of a column.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            Column type (e.g., 'enum', 'varchar', 'integer', 'numeric', 'timestamp')
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta:
            return None

        return col_meta.get('type')

    def get_numeric_range(self, table_name: str, column_name: str) -> Optional[tuple]:
        """
        Get the valid range for a numeric column.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            Tuple of (min, max) or None if not a numeric column with range
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta or col_meta.get('type') != 'numeric':
            return None

        range_val = col_meta.get('range')
        if range_val and isinstance(range_val, list) and len(range_val) == 2:
            return tuple(range_val)

        return None

    def get_table_names(self) -> List[str]:
        """
        Get all table names that have metadata.

        Returns:
            List of table names
        """
        return list(self.metadata.keys())

    def get_column_description(self, table_name: str, column_name: str) -> Optional[str]:
        """
        Get human-readable description of a column.

        Args:
            table_name: Table name
            column_name: Column name

        Returns:
            Column description or None
        """
        col_meta = self.get_column_metadata(table_name, column_name)
        if not col_meta:
            return None

        return col_meta.get('description')

    def get_table_metadata(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get all metadata for a table including column_metadata.

        Args:
            table_name: Table name (can be schema-qualified)

        Returns:
            Dict with 'column_metadata' key containing all column metadata
        """
        if table_name not in self.metadata:
            return None

        return {'column_metadata': self.metadata[table_name]}

    def get_api_parameter_metadata(self, endpoint_name: str, parameter_name: str) -> Optional[Dict[str, Any]]:
        """
        Get parameter metadata for a REST API endpoint.

        Args:
            endpoint_name: REST API endpoint name (e.g., 'search_cases')
            parameter_name: Parameter name (e.g., 'status', 'priority')

        Returns:
            Parameter metadata dict with 'type', 'description', 'possible_values', etc.
            or None if not found
        """
        if endpoint_name not in self.api_metadata:
            return None

        endpoint_params = self.api_metadata[endpoint_name]
        return endpoint_params.get(parameter_name)

    def get_soap_parameter_metadata(self, operation_name: str, parameter_name: str) -> Optional[Dict[str, Any]]:
        """
        Get parameter metadata for a SOAP operation.

        Args:
            operation_name: SOAP operation name (e.g., 'get_customer_details')
            parameter_name: Parameter name (e.g., 'customerId', 'includeHistory')

        Returns:
            Parameter metadata dict with 'type', 'description', 'required', etc.
            or None if not found
        """
        if operation_name not in self.soap_metadata:
            return None

        operation_params = self.soap_metadata[operation_name]
        return operation_params.get(parameter_name)


# Global singleton instance
_metadata_manager: Optional[MetadataManager] = None


def get_metadata_manager() -> MetadataManager:
    """
    Get the global MetadataManager singleton instance.

    Returns:
        MetadataManager instance
    """
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataManager()
    return _metadata_manager
