"""
Filter Generator for creating dynamic database queries and API filters
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import re
import logging

from app.intelligence.metadata_manager import get_metadata_manager, MetadataManager

logger = logging.getLogger(__name__)


class FilterOperator(Enum):
    """Filter operators"""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT IN"
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    ILIKE = "ILIKE"  # PostgreSQL case-insensitive LIKE
    NOT_ILIKE = "NOT ILIKE"
    BETWEEN = "BETWEEN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


@dataclass
class FilterCondition:
    """Single filter condition"""
    field: str
    operator: FilterOperator
    value: Any
    data_type: str  # "string", "number", "date", "boolean"


@dataclass
class GeneratedFilter:
    """Generated filter with multiple output formats"""
    conditions: List[FilterCondition]
    sql_where_clause: str
    api_query_params: Dict[str, Any]
    mongodb_query: Dict[str, Any]
    description: str


class FilterGenerator:
    """
    Generates filters for different data sources from natural language queries
    Converts user intent into executable filters
    """

    def __init__(self, metadata_manager: Optional[MetadataManager] = None):
        """
        Initialize filter generator.

        Args:
            metadata_manager: MetadataManager instance for enum value normalization
        """
        self.metadata_manager = metadata_manager or get_metadata_manager()
        self.table_name: Optional[str] = None  # Set by caller before generating filters
        self.metadata_source: Optional[str] = None  # 'database', 'rest_api', or 'soap_api'

        self.date_patterns = {
            "today": lambda: datetime.now().date(),
            "yesterday": lambda: (datetime.now() - timedelta(days=1)).date(),
            "this week": lambda: (datetime.now() - timedelta(days=datetime.now().weekday())).date(),
            "this month": lambda: datetime.now().replace(day=1).date(),
            "last 7 days": lambda: (datetime.now() - timedelta(days=7)).date(),
            "last 30 days": lambda: (datetime.now() - timedelta(days=30)).date(),
        }

    def set_table_context(self, table_name: str):
        """
        Set the table context for metadata-aware filtering.

        Args:
            table_name: Table name (can be schema-qualified)
        """
        self.table_name = table_name

    def set_metadata_source(self, source: str):
        """
        Set the metadata source type for validation.

        Args:
            source: 'database', 'rest_api', or 'soap_api'
        """
        self.metadata_source = source

    def _normalize_enum_value(self, column_name: str, user_value: str) -> str:
        """
        Normalize enum value using metadata (case-insensitive matching).

        Args:
            column_name: Column name
            user_value: Value from user query

        Returns:
            Normalized value with correct case, or original value if not enum

        Example:
            _normalize_enum_value("status", "open") -> "Open"
            _normalize_enum_value("status", "OPEN") -> "Open"
        """
        if not self.table_name:
            return user_value

        # Try to normalize using metadata
        normalized = self.metadata_manager.normalize_enum_value(
            self.table_name, column_name, user_value
        )

        if normalized:
            logger.debug(f"Normalized '{user_value}' -> '{normalized}' for {self.table_name}.{column_name}")
            return normalized

        # Return original if no metadata or not an enum
        return user_value

    def _get_field_metadata(self, field_name: str) -> Optional[Dict[str, Any]]:
        """
        Get field metadata from appropriate source based on metadata_source.

        For database queries: Returns column metadata from database_schemas.yaml
        For REST API queries: Returns parameter metadata from api_endpoints.yaml
        For SOAP API queries: Returns parameter metadata from soap_endpoints.yaml

        Args:
            field_name: Field/parameter name to look up

        Returns:
            Field metadata dict with 'type', 'description', 'possible_values', etc.
            or None if field not found
        """
        if not self.metadata_manager:
            return None

        # For database queries
        if self.metadata_source == 'database' and self.table_name:
            table_metadata = self.metadata_manager.get_table_metadata(self.table_name)
            if table_metadata and 'column_metadata' in table_metadata:
                return table_metadata['column_metadata'].get(field_name)

        # For REST API queries
        elif self.metadata_source == 'rest_api':
            api_metadata = self.metadata_manager.get_api_parameter_metadata(self.table_name, field_name)
            return api_metadata

        # For SOAP API queries
        elif self.metadata_source == 'soap_api':
            soap_metadata = self.metadata_manager.get_soap_parameter_metadata(self.table_name, field_name)
            return soap_metadata

        return None

    def _infer_data_type_from_metadata(self, field_metadata: Dict[str, Any]) -> str:
        """
        Infer FilterCondition data type from metadata type.

        Maps metadata types to FilterCondition data types:
        - varchar, text, string → "string"
        - integer, bigint, int → "number"
        - numeric, decimal, double precision, float → "number"
        - boolean, bool → "boolean"
        - timestamp, date, datetime → "date"

        Args:
            field_metadata: Field metadata dictionary

        Returns:
            Data type string: "string", "number", "boolean", or "date"
        """
        metadata_type = field_metadata.get('type', '').lower()

        # String types
        if metadata_type in ['varchar', 'text', 'string', 'char']:
            return 'string'

        # Numeric types
        if metadata_type in ['integer', 'bigint', 'int', 'numeric', 'decimal', 'double precision', 'float', 'number']:
            return 'number'

        # Boolean types
        if metadata_type in ['boolean', 'bool']:
            return 'boolean'

        # Date/time types
        if metadata_type in ['timestamp', 'date', 'datetime']:
            return 'date'

        # Default to string
        return 'string'

    async def generate_filters(
        self,
        query: str,
        schema: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> GeneratedFilter:
        """
        Generate filters from natural language query

        Args:
            query: User query
            schema: Schema information for the target data source
            context: Additional context (existing filters, user preferences)

        Returns:
            GeneratedFilter with multiple format outputs
        """
        conditions = []

        # Extract filter conditions from query
        # NEW: Extract generic filters FIRST (highest priority - metadata-driven)
        conditions.extend(self._extract_generic_equality_filters(query))
        conditions.extend(self._extract_natural_language_like_filters(query))

        # Existing hardcoded extractors (fallback)
        conditions.extend(self._extract_status_filters(query))
        conditions.extend(self._extract_priority_filters(query))
        conditions.extend(self._extract_date_filters(query))
        conditions.extend(self._extract_id_filters(query))
        conditions.extend(self._extract_text_filters(query, schema))
        conditions.extend(self._extract_numeric_filters(query, schema))

        # Add context filters
        if context and "filters" in context:
            conditions.extend(self._context_to_conditions(context["filters"]))

        # Generate output formats
        sql_where = self._generate_sql_where(conditions)
        api_params = self._generate_api_params(conditions)
        mongo_query = self._generate_mongodb_query(conditions)
        description = self._generate_description(conditions)

        return GeneratedFilter(
            conditions=conditions,
            sql_where_clause=sql_where,
            api_query_params=api_params,
            mongodb_query=mongo_query,
            description=description
        )

    def _extract_status_filters(self, query: str) -> List[FilterCondition]:
        """Extract status filter conditions with metadata normalization"""
        conditions = []
        query_lower = query.lower()

        status_keywords = {
            "open": ["open", "active", "ongoing"],
            "closed": ["closed", "resolved", "completed"],
            "pending": ["pending", "waiting", "in progress"],
            "cancelled": ["cancelled", "canceled", "rejected"]
        }

        for status, keywords in status_keywords.items():
            if any(kw in query_lower for kw in keywords):
                # Normalize using metadata (e.g., "open" -> "Open")
                normalized_status = self._normalize_enum_value("status", status)

                conditions.append(FilterCondition(
                    field="status",
                    operator=FilterOperator.EQUALS,
                    value=normalized_status,
                    data_type="string"
                ))
                break  # Only one status filter

        return conditions

    def _extract_priority_filters(self, query: str) -> List[FilterCondition]:
        """Extract priority filter conditions with metadata normalization"""
        conditions = []
        query_lower = query.lower()

        priority_map = {
            "high priority": "high",
            "medium priority": "medium",
            "low priority": "low"
        }

        for keyword, priority_value in priority_map.items():
            if keyword in query_lower:
                # Normalize using metadata (e.g., "high" -> "High")
                normalized_priority = self._normalize_enum_value("priority", priority_value)

                conditions.append(FilterCondition(
                    field="priority",
                    operator=FilterOperator.EQUALS,
                    value=normalized_priority,
                    data_type="string"
                ))
                break

        return conditions

    def _extract_date_filters(self, query: str) -> List[FilterCondition]:
        """Extract date range filter conditions"""
        conditions = []
        query_lower = query.lower()

        for pattern, date_func in self.date_patterns.items():
            if pattern in query_lower:
                start_date = date_func()

                # Determine date field from query
                date_field = "created_at"  # Default
                if "updated" in query_lower or "modified" in query_lower:
                    date_field = "updated_at"
                elif "closed" in query_lower:
                    date_field = "closed_at"

                conditions.append(FilterCondition(
                    field=date_field,
                    operator=FilterOperator.GREATER_EQUAL,
                    value=start_date.isoformat(),
                    data_type="date"
                ))
                break

        return conditions

    def _extract_id_filters(self, query: str) -> List[FilterCondition]:
        """Extract ID filter conditions"""
        conditions = []

        # Extract case IDs (#12345)
        case_ids = re.findall(r'#(\d+)', query)
        if case_ids:
            if len(case_ids) == 1:
                conditions.append(FilterCondition(
                    field="id",
                    operator=FilterOperator.EQUALS,
                    value=int(case_ids[0]),
                    data_type="number"
                ))
            else:
                conditions.append(FilterCondition(
                    field="id",
                    operator=FilterOperator.IN,
                    value=[int(cid) for cid in case_ids],
                    data_type="number"
                ))

        # Extract alert IDs (e.g., "alert AML_20241120225734_LAY456789", "alert_id: XYZ123")
        # Patterns to match:
        # 1. "alert [ID]" or "alert_id [ID]"
        # 2. "alert_id = [ID]" or "alert_id: [ID]"
        alert_id_patterns = [
            r'alert\s+([A-Z0-9_-]+)',  # "alert AML_20241120225734_LAY456789"
            r'alert_id\s*[=:]\s*["\']?([A-Z0-9_-]+)["\']?',  # "alert_id = AML_..." or "alert_id: AML_..."
            r'alert_id\s+([A-Z0-9_-]+)',  # "alert_id AML_..."
        ]

        for pattern in alert_id_patterns:
            alert_ids = re.findall(pattern, query, re.IGNORECASE)
            if alert_ids:
                # Use the first match found
                conditions.append(FilterCondition(
                    field="alert_id",
                    operator=FilterOperator.EQUALS,
                    value=alert_ids[0],
                    data_type="string"
                ))
                break  # Stop after first match to avoid duplicates

        return conditions

    def _extract_text_filters(
        self,
        query: str,
        schema: Optional[Dict[str, Any]]
    ) -> List[FilterCondition]:
        """Extract text search filter conditions"""
        conditions = []

        # Look for quoted strings (exact match)
        quoted_strings = re.findall(r'"([^"]+)"', query)
        if quoted_strings:
            # Determine search field from schema
            search_field = "title"  # Default
            if schema and "fields" in schema:
                # Prefer description or title fields
                fields = schema["fields"].keys()
                if "description" in fields:
                    search_field = "description"
                elif "name" in fields:
                    search_field = "name"

            for search_term in quoted_strings:
                conditions.append(FilterCondition(
                    field=search_field,
                    operator=FilterOperator.LIKE,
                    value=f"%{search_term}%",
                    data_type="string"
                ))

        return conditions

    def _extract_numeric_filters(
        self,
        query: str,
        schema: Optional[Dict[str, Any]]
    ) -> List[FilterCondition]:
        """Extract numeric comparison filters"""
        conditions = []

        # Extract patterns like "amount > 1000", "count less than 50"
        patterns = [
            (r'(\w+)\s*>\s*(\d+)', FilterOperator.GREATER_THAN),
            (r'(\w+)\s*<\s*(\d+)', FilterOperator.LESS_THAN),
            (r'(\w+)\s*>=\s*(\d+)', FilterOperator.GREATER_EQUAL),
            (r'(\w+)\s*<=\s*(\d+)', FilterOperator.LESS_EQUAL),
            (r'(\w+)\s+greater than\s+(\d+)', FilterOperator.GREATER_THAN),
            (r'(\w+)\s+less than\s+(\d+)', FilterOperator.LESS_THAN),
        ]

        query_lower = query.lower()
        for pattern, operator in patterns:
            matches = re.findall(pattern, query_lower)
            for field, value in matches:
                conditions.append(FilterCondition(
                    field=field,
                    operator=operator,
                    value=int(value),
                    data_type="number"
                ))

        return conditions

    def _extract_generic_equality_filters(self, query: str) -> List[FilterCondition]:
        """
        Extract generic field=value filters using metadata validation.
        Works for ALL data sources (database, REST API, SOAP API).

        Supports patterns:
        - focal_entity = '3189446387'
        - customer_id = 12345
        - total_score > 90
        - status != 'Closed'
        - focal_entity LIKE 'ACC%'
        - name NOT LIKE '%test%'
        - email ILIKE '%@gmail.com'

        Validates fields against metadata from:
        - database_schemas.yaml (for database queries)
        - api_endpoints.yaml (for REST APIs)
        - soap_endpoints.yaml (for SOAP APIs)
        """
        conditions = []

        # Regex pattern to match: field operator value
        # Handles: field = value, field='value', field LIKE '%value%', etc.
        pattern = r"(\w+)\s*(=|!=|>|<|>=|<=|LIKE|NOT\s+LIKE|ILIKE|NOT\s+ILIKE)\s*'?([^']+)'?"

        for match in re.finditer(pattern, query, re.IGNORECASE):
            field_name = match.group(1).strip()
            operator_str = match.group(2).strip().upper()
            value = match.group(3).strip()

            # Validate field against metadata
            field_metadata = self._get_field_metadata(field_name)
            if not field_metadata:
                logger.debug(f"Field '{field_name}' not found in metadata, skipping")
                continue

            # Map operator string to FilterOperator enum
            operator_map = {
                '=': FilterOperator.EQUALS,
                '!=': FilterOperator.NOT_EQUALS,
                '>': FilterOperator.GREATER_THAN,
                '<': FilterOperator.LESS_THAN,
                '>=': FilterOperator.GREATER_EQUAL,
                '<=': FilterOperator.LESS_EQUAL,
                'LIKE': FilterOperator.LIKE,
                'NOT LIKE': FilterOperator.NOT_LIKE,
                'ILIKE': FilterOperator.ILIKE,
                'NOT ILIKE': FilterOperator.NOT_ILIKE,
            }

            operator = operator_map.get(operator_str)
            if not operator:
                logger.debug(f"Unsupported operator '{operator_str}', skipping")
                continue

            # Infer data type from metadata
            data_type = self._infer_data_type_from_metadata(field_metadata)

            # Normalize enum values if applicable
            if field_metadata.get('type') == 'enum' or 'possible_values' in field_metadata:
                value = self._normalize_enum_value(field_name, value)

            # Create filter condition
            conditions.append(FilterCondition(
                field=field_name,
                operator=operator,
                value=value,
                data_type=data_type
            ))

            logger.debug(f"Extracted filter: {field_name} {operator_str} {value} (type: {data_type})")

        return conditions

    def _extract_natural_language_like_filters(self, query: str) -> List[FilterCondition]:
        """
        Extract LIKE filters from natural language patterns.

        Supports:
        - "field contains value" → field LIKE '%value%'
        - "field starts with value" → field LIKE 'value%'
        - "field ends with value" → field LIKE '%value'
        - "field includes value" → field LIKE '%value%'
        """
        conditions = []
        query_lower = query.lower()

        # Pattern 1: "field contains/includes value"
        contains_patterns = [
            r'(\w+)\s+(?:contains|includes)\s+["\']?([^"\']+)["\']?',
        ]

        for pattern in contains_patterns:
            for match in re.finditer(pattern, query_lower, re.IGNORECASE):
                field_name = match.group(1).strip()
                value = match.group(2).strip()

                # Validate field
                if not self._get_field_metadata(field_name):
                    continue

                conditions.append(FilterCondition(
                    field=field_name,
                    operator=FilterOperator.LIKE,
                    value=f"%{value}%",
                    data_type="string"
                ))

        # Pattern 2: "field starts with/beginning with value"
        starts_patterns = [
            r'(\w+)\s+(?:starts\s+with|beginning\s+with|begins\s+with)\s+["\']?([^"\']+)["\']?',
        ]

        for pattern in starts_patterns:
            for match in re.finditer(pattern, query_lower, re.IGNORECASE):
                field_name = match.group(1).strip()
                value = match.group(2).strip()

                if not self._get_field_metadata(field_name):
                    continue

                conditions.append(FilterCondition(
                    field=field_name,
                    operator=FilterOperator.LIKE,
                    value=f"{value}%",
                    data_type="string"
                ))

        # Pattern 3: "field ends with/ending with value"
        ends_patterns = [
            r'(\w+)\s+(?:ends\s+with|ending\s+with)\s+["\']?([^"\']+)["\']?',
        ]

        for pattern in ends_patterns:
            for match in re.finditer(pattern, query_lower, re.IGNORECASE):
                field_name = match.group(1).strip()
                value = match.group(2).strip()

                if not self._get_field_metadata(field_name):
                    continue

                conditions.append(FilterCondition(
                    field=field_name,
                    operator=FilterOperator.LIKE,
                    value=f"%{value}",
                    data_type="string"
                ))

        return conditions

    def _context_to_conditions(self, filters: Dict[str, Any]) -> List[FilterCondition]:
        """Convert context filters to filter conditions"""
        conditions = []

        for field, value in filters.items():
            # Determine operator and data type
            operator = FilterOperator.EQUALS
            data_type = "string"

            if isinstance(value, bool):
                data_type = "boolean"
            elif isinstance(value, int) or isinstance(value, float):
                data_type = "number"
            elif isinstance(value, list):
                operator = FilterOperator.IN
                if value and isinstance(value[0], int):
                    data_type = "number"

            conditions.append(FilterCondition(
                field=field,
                operator=operator,
                value=value,
                data_type=data_type
            ))

        return conditions

    def _generate_sql_where(self, conditions: List[FilterCondition]) -> str:
        """
        Generate SQL WHERE clause with support for all operators.

        Handles: =, !=, >, <, >=, <=, LIKE, NOT LIKE, ILIKE, NOT ILIKE, IN, IS NULL, etc.
        """
        if not conditions:
            return ""

        clauses = []
        for condition in conditions:
            field = condition.field
            operator = condition.operator.value
            value = condition.value

            # LIKE operators (includes LIKE, NOT LIKE, ILIKE, NOT ILIKE)
            if condition.operator in [FilterOperator.LIKE, FilterOperator.NOT_LIKE,
                                       FilterOperator.ILIKE, FilterOperator.NOT_ILIKE]:
                clause = f"{field} {operator} '{value}'"

            # IN operator
            elif condition.operator == FilterOperator.IN:
                if condition.data_type == "string":
                    value_str = ", ".join(f"'{v}'" for v in value)
                else:
                    value_str = ", ".join(str(v) for v in value)
                clause = f"{field} IN ({value_str})"

            # NULL operators
            elif condition.operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
                clause = f"{field} {operator}"

            # String values - quote them
            elif condition.data_type == "string":
                clause = f"{field} {operator} '{value}'"

            # Numeric/boolean/date values - no quotes
            else:
                clause = f"{field} {operator} {value}"

            clauses.append(clause)

        return " AND ".join(clauses)

    def _generate_api_params(self, conditions: List[FilterCondition]) -> Dict[str, Any]:
        """
        Generate API query parameters for REST/SOAP APIs.

        Maps filter conditions to JSON parameters:
        - Simple equality: {field: value}
        - LIKE patterns: {field_contains: value} or {field_starts: value} or {field_ends: value}
        - Comparisons: {field_gt: value}, {field_lt: value}, etc.
        """
        params = {}

        for condition in conditions:
            field = condition.field
            value = condition.value

            # Simple equality - most common for REST/SOAP
            if condition.operator == FilterOperator.EQUALS:
                params[field] = value

            # Not equals
            elif condition.operator == FilterOperator.NOT_EQUALS:
                params[f"{field}_ne"] = value

            # LIKE operators - convert wildcard patterns to REST-friendly params
            elif condition.operator in [FilterOperator.LIKE, FilterOperator.ILIKE]:
                # Determine pattern type based on wildcard position
                if value.startswith('%') and value.endswith('%'):
                    # Contains pattern: %value%
                    params[f"{field}_contains"] = value.strip('%')
                elif value.startswith('%'):
                    # Ends with pattern: %value
                    params[f"{field}_ends"] = value.lstrip('%')
                elif value.endswith('%'):
                    # Starts with pattern: value%
                    params[f"{field}_starts"] = value.rstrip('%')
                else:
                    # Exact match (no wildcards)
                    params[field] = value

            # Comparison operators
            elif condition.operator == FilterOperator.GREATER_THAN:
                params[f"{field}_gt"] = value
            elif condition.operator == FilterOperator.LESS_THAN:
                params[f"{field}_lt"] = value
            elif condition.operator == FilterOperator.GREATER_EQUAL:
                params[f"{field}_gte"] = value
            elif condition.operator == FilterOperator.LESS_EQUAL:
                params[f"{field}_lte"] = value

            # IN operator
            elif condition.operator == FilterOperator.IN:
                if isinstance(value, list):
                    params[field] = ",".join(str(v) for v in value)
                else:
                    params[field] = value

        return params

    def _generate_mongodb_query(self, conditions: List[FilterCondition]) -> Dict[str, Any]:
        """Generate MongoDB query"""
        if not conditions:
            return {}

        query = {}

        for condition in conditions:
            field = condition.field
            value = condition.value

            if condition.operator == FilterOperator.EQUALS:
                query[field] = value
            elif condition.operator == FilterOperator.NOT_EQUALS:
                query[field] = {"$ne": value}
            elif condition.operator == FilterOperator.GREATER_THAN:
                query[field] = {"$gt": value}
            elif condition.operator == FilterOperator.LESS_THAN:
                query[field] = {"$lt": value}
            elif condition.operator == FilterOperator.GREATER_EQUAL:
                query[field] = {"$gte": value}
            elif condition.operator == FilterOperator.LESS_EQUAL:
                query[field] = {"$lte": value}
            elif condition.operator == FilterOperator.IN:
                query[field] = {"$in": value}
            elif condition.operator == FilterOperator.NOT_IN:
                query[field] = {"$nin": value}
            elif condition.operator == FilterOperator.LIKE:
                # Convert SQL LIKE to MongoDB regex
                regex_pattern = value.replace("%", ".*")
                query[field] = {"$regex": regex_pattern, "$options": "i"}

        return query

    def _generate_description(self, conditions: List[FilterCondition]) -> str:
        """Generate human-readable description of filters"""
        if not conditions:
            return "No filters applied"

        descriptions = []
        for condition in conditions:
            field = condition.field.replace("_", " ").title()
            operator = condition.operator.value
            value = condition.value

            if condition.operator == FilterOperator.EQUALS:
                desc = f"{field} is {value}"
            elif condition.operator == FilterOperator.IN:
                desc = f"{field} is one of {', '.join(str(v) for v in value)}"
            elif condition.operator == FilterOperator.LIKE:
                desc = f"{field} contains '{value.strip('%')}'"
            elif condition.operator == FilterOperator.GREATER_THAN:
                desc = f"{field} greater than {value}"
            elif condition.operator == FilterOperator.LESS_THAN:
                desc = f"{field} less than {value}"
            elif condition.operator == FilterOperator.GREATER_EQUAL:
                desc = f"{field} greater than or equal to {value}"
            elif condition.operator == FilterOperator.LESS_EQUAL:
                desc = f"{field} less than or equal to {value}"
            else:
                desc = f"{field} {operator} {value}"

            descriptions.append(desc)

        return "; ".join(descriptions)

    def combine_filters(
        self,
        filter1: GeneratedFilter,
        filter2: GeneratedFilter,
        combine_type: str = "AND"
    ) -> GeneratedFilter:
        """
        Combine two filter sets

        Args:
            filter1: First filter
            filter2: Second filter
            combine_type: "AND" or "OR"

        Returns:
            Combined GeneratedFilter
        """
        combined_conditions = filter1.conditions + filter2.conditions

        # Regenerate all formats
        sql_where = self._generate_sql_where(combined_conditions)
        if combine_type == "OR":
            sql_where = f"({filter1.sql_where_clause}) OR ({filter2.sql_where_clause})"

        api_params = {**filter1.api_query_params, **filter2.api_query_params}
        mongo_query = {**filter1.mongodb_query, **filter2.mongodb_query}
        description = f"({filter1.description}) {combine_type} ({filter2.description})"

        return GeneratedFilter(
            conditions=combined_conditions,
            sql_where_clause=sql_where,
            api_query_params=api_params,
            mongodb_query=mongo_query,
            description=description
        )
