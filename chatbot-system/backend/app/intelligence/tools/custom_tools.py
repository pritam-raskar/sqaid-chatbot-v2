"""
Custom tool wrappers that properly extend LangChain's BaseTool
These tools wrap specific endpoints/tables with pre-configured settings
"""
from typing import Optional, Any, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging
import json

from app.intelligence.tools.api_tool import RESTAPIInput, SOAPAPIInput
from app.intelligence.tools.database_tool import DatabaseQueryInput
from app.data_access.adapters.rest_adapter import RESTAdapter
from app.data.soap_adapter import SOAPAdapter
from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter
from app.data_access.adapters.oracle_adapter import OracleAdapter
from app.intelligence.filter_generator import FilterGenerator

logger = logging.getLogger(__name__)


class ConfiguredRESTTool(BaseTool):
    """REST API tool configured for a specific endpoint"""

    name: str
    description: str
    args_schema: Type[BaseModel] = RESTAPIInput

    # Configuration
    endpoint_url: str = ""
    http_method: str = "GET"
    api_adapter: Optional[RESTAdapter] = None
    base_url: Optional[str] = None
    filter_generator: Optional[FilterGenerator] = None  # For natural language filter support

    class Config:
        arbitrary_types_allowed = True

    def _run(self, endpoint: str = "", method: str = "", params: Optional[str] = None,
             body: Optional[str] = None, run_manager=None) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(endpoint, method, params, body, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(endpoint, method, params, body, run_manager)
            )

    async def _arun(self, endpoint: str = "", method: str = "", params: Optional[str] = None,
                    body: Optional[str] = None, run_manager=None) -> str:
        """Execute REST API call with pre-configured endpoint"""
        try:
            # Use configured values if not provided
            if not endpoint:
                endpoint = self.endpoint_url
            if not method:
                method = self.http_method

            # Initialize adapter if not set
            if not self.api_adapter:
                if not self.base_url:
                    return "Error: REST API adapter not configured"
                self.api_adapter = RESTAdapter(config={
                    'base_url': self.base_url,
                    'config': {'base_url': self.base_url}
                })

            # Parse parameters - support both JSON and natural language
            query_params = {}
            if params:
                # Try parsing as JSON first (backwards compatible)
                try:
                    query_params = json.loads(params)
                except json.JSONDecodeError:
                    # Fallback to natural language filtering
                    logger.info(f"Parsing params as natural language: {params}")

                    if not self.filter_generator:
                        from app.intelligence.filter_generator import FilterGenerator
                        self.filter_generator = FilterGenerator()

                    # Set metadata source for REST API
                    self.filter_generator.set_metadata_source('rest_api')
                    self.filter_generator.set_table_context(self.name)  # Use tool name as context

                    # Generate filters from natural language
                    generated_filter = await self.filter_generator.generate_filters(params)
                    query_params = generated_filter.api_query_params

                    logger.info(f"Generated API params: {query_params}")

            # Parse body
            request_body = None
            if body:
                try:
                    request_body = json.loads(body) if body else None
                except json.JSONDecodeError:
                    return f"Error: Invalid JSON in body: {body}"

            # Call API
            if method.upper() == "GET":
                response = await self.api_adapter.query(endpoint, params=query_params)
            elif method.upper() in ["POST", "PUT", "PATCH"]:
                response = await self.api_adapter.execute(
                    endpoint,
                    method=method.upper(),
                    json=request_body,
                    params=query_params
                )
            elif method.upper() == "DELETE":
                response = await self.api_adapter.execute(
                    endpoint,
                    method="DELETE",
                    params=query_params
                )
            else:
                return f"Error: Unsupported HTTP method: {method}"

            # Format response
            if isinstance(response, dict) or isinstance(response, list):
                return json.dumps(response, indent=2)
            else:
                return str(response)

        except Exception as e:
            logger.error(f"REST API call failed: {e}")
            return f"Error calling REST API: {str(e)}"


class ConfiguredSOAPTool(BaseTool):
    """SOAP API tool configured for a specific operation"""

    name: str
    description: str
    args_schema: Type[BaseModel] = SOAPAPIInput

    # Configuration
    operation_name: str = ""
    soap_adapter: Optional[SOAPAdapter] = None
    wsdl_url: Optional[str] = None
    filter_generator: Optional[FilterGenerator] = None  # For natural language filter support

    class Config:
        arbitrary_types_allowed = True

    def _run(self, action: str = "", parameters: str = "", run_manager=None) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(action, parameters, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(self._arun(action, parameters, run_manager))

    async def _arun(self, action: str = "", parameters: str = "", run_manager=None) -> str:
        """Execute SOAP call with pre-configured operation"""
        try:
            # Use configured operation if not provided
            if not action:
                action = self.operation_name

            if not self.soap_adapter:
                return "Error: SOAP adapter not configured"

            # Parse parameters - support both JSON and natural language
            params = {}
            if parameters:
                # Try parsing as JSON first (backwards compatible)
                try:
                    params = json.loads(parameters)
                except json.JSONDecodeError:
                    # Fallback to natural language filtering
                    logger.info(f"Parsing SOAP parameters as natural language: {parameters}")

                    if not self.filter_generator:
                        from app.intelligence.filter_generator import FilterGenerator
                        self.filter_generator = FilterGenerator()

                    # Set metadata source for SOAP API
                    self.filter_generator.set_metadata_source('soap_api')
                    self.filter_generator.set_table_context(self.name)  # Use tool name as context

                    # Generate filters from natural language
                    generated_filter = await self.filter_generator.generate_filters(parameters)
                    params = generated_filter.api_query_params

                    logger.info(f"Generated SOAP params: {params}")

            # Call SOAP service
            response = await self.soap_adapter.query(action, **params)

            # Format response
            if isinstance(response, dict) or isinstance(response, list):
                return json.dumps(response, indent=2)
            else:
                return str(response)

        except Exception as e:
            logger.error(f"SOAP call failed: {e}")
            return f"Error calling SOAP service: {str(e)}"


class ConfiguredDatabaseTool(BaseTool):
    """Database query tool configured for a specific table"""

    name: str
    description: str
    args_schema: Type[BaseModel] = DatabaseQueryInput

    # Configuration
    table_name: str = ""
    db_adapter: Optional[Any] = None  # PostgreSQLAdapter or OracleAdapter
    filter_generator: Optional[FilterGenerator] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(self, table: str = "", columns: Optional[str] = None,
             filters: Optional[str] = None, group_by: Optional[str] = None,
             limit: int = 100, order_by: Optional[str] = None, run_manager=None) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(table, columns, filters, group_by, limit, order_by, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(table, columns, filters, group_by, limit, order_by, run_manager)
            )

    async def _arun(self, table: str = "", columns: Optional[str] = None,
                    filters: Optional[str] = None, group_by: Optional[str] = None,
                    limit: int = 100, order_by: Optional[str] = None, run_manager=None) -> str:
        """Execute database query with pre-configured table"""
        try:
            # Always use configured table (which has schema qualification)
            # Ignore the table parameter from LLM as it may not include schema
            table = self.table_name

            if not self.db_adapter:
                return "Error: Database adapter not configured"

            # Validate table name (prevent SQL injection)
            if not self._is_valid_identifier(table):
                return f"Error: Invalid table name '{table}'"

            # Build SELECT clause
            select_columns = columns if columns else "*"
            if not self._is_valid_column_list(select_columns):
                return f"Error: Invalid column specification"

            # Build WHERE clause from natural language filters
            where_clause = ""
            if filters:
                if not self.filter_generator:
                    self.filter_generator = FilterGenerator()

                # Set table context for metadata-aware enum normalization
                self.filter_generator.set_table_context(table)

                # Set metadata source for field validation
                self.filter_generator.set_metadata_source('database')

                generated_filter = await self.filter_generator.generate_filters(filters)
                where_clause = generated_filter.sql_where_clause
                if where_clause:
                    where_clause = f"WHERE {where_clause}"

            # Build GROUP BY clause
            group_clause = ""
            if group_by:
                # Validate group_by columns
                group_cols = [col.strip() for col in group_by.split(',')]
                for col in group_cols:
                    if not self._is_valid_identifier(col):
                        return f"Error: Invalid group_by column '{col}'"
                group_clause = f"GROUP BY {group_by}"

            # Build ORDER BY clause
            order_clause = ""
            if order_by:
                if not self._is_valid_identifier(order_by.split()[0]):  # Allow "column DESC"
                    return f"Error: Invalid order_by column"
                order_clause = f"ORDER BY {order_by}"

            # Build complete query
            query = f"""
                SELECT {select_columns}
                FROM {table}
                {where_clause}
                {group_clause}
                {order_clause}
                LIMIT {limit}
            """.strip()

            logger.info(f"Executing query: {query}")

            # Execute query - PostgreSQLAdapter uses execute_query, not query
            if hasattr(self.db_adapter, 'execute_query'):
                results = await self.db_adapter.execute_query(query)
            elif hasattr(self.db_adapter, 'query'):
                results = await self.db_adapter.query(query)
            else:
                return "Error: Database adapter has no query method"

            logger.info(f"Query returned {len(results) if results else 0} results")
            if results:
                logger.info(f"First result: {results[0]}")

            # Format results
            formatted_result = self._format_results(results, table)
            logger.info(f"Formatted result: {formatted_result[:200]}...")
            return formatted_result

        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return f"Error executing database query: {str(e)}"

    def _is_valid_identifier(self, identifier: str) -> bool:
        """Validate SQL identifier to prevent injection"""
        if not identifier:
            return False
        # Allow alphanumeric, underscore, and dots for schema.table
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_\.]*$', identifier.strip()))

    def _is_valid_column_list(self, columns: str) -> bool:
        """Validate column list - allow SQL functions and aliases"""
        if columns == "*":
            return True
        # Allow common SQL patterns: COUNT(*), SUM(col), col AS alias, etc.
        # Basic validation to prevent obvious SQL injection
        import re
        # Allow: alphanumeric, underscore, dot, comma, parentheses, spaces, AS keyword, asterisk
        safe_pattern = r'^[a-zA-Z0-9_\.\,\(\)\*\s]+(?:\s+(?:AS|as)\s+[a-zA-Z0-9_]+)?(?:\s*,\s*[a-zA-Z0-9_\.\,\(\)\*\s]+(?:\s+(?:AS|as)\s+[a-zA-Z0-9_]+)?)*$'
        return bool(re.match(safe_pattern, columns.strip()))

    def _format_results(self, results: list, table: str) -> str:
        """Format query results for LLM consumption"""
        if not results:
            return f"No records found in {table}."

        formatted = f"Found {len(results)} record(s) from {table}:\n\n"

        # Show first 10 results in detail
        for i, record in enumerate(results[:10], 1):
            formatted += f"{i}. "
            # Format each field
            fields = [f"{k}: {v}" for k, v in record.items()]
            formatted += ", ".join(fields)
            formatted += "\n"

        if len(results) > 10:
            formatted += f"\n... and {len(results) - 10} more records"

        return formatted