"""
LangChain tools for generic database queries
"""
from typing import Optional, Type, Any, Dict, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter
from app.intelligence.filter_generator import FilterGenerator

logger = logging.getLogger(__name__)


class DatabaseQueryInput(BaseModel):
    """Input schema for database query tool"""
    table: str = Field(..., description="Table name to query")
    columns: Optional[str] = Field(None, description="Columns to select (comma-separated, default: *). Can include aggregation functions like COUNT(*), SUM(column), etc.")
    filters: Optional[str] = Field(None, description="Natural language filters (e.g., 'status is open and priority is high')")
    group_by: Optional[str] = Field(None, description="Column(s) to group by (comma-separated). Required when using aggregate functions in columns.")
    limit: Optional[int] = Field(100, description="Maximum number of results")
    order_by: Optional[str] = Field(None, description="Column to order by")


class DatabaseAggregateInput(BaseModel):
    """Input schema for database aggregation tool"""
    table: str = Field(..., description="Table name to query")
    operation: str = Field(..., description="Aggregation operation (count, sum, avg, max, min)")
    column: Optional[str] = Field(None, description="Column to aggregate (required for sum, avg, max, min)")
    group_by: Optional[str] = Field(None, description="Column to group by")
    filters: Optional[str] = Field(None, description="Natural language filters")


class DatabaseQueryTool(BaseTool):
    """
    Generic tool for querying any database table with flexible filtering
    Supports PostgreSQL and Oracle databases
    """

    name: str = "query_database"
    description: str = """
    Query any database table with flexible filtering and ordering.
    Use this for general database queries when no specific tool exists.

    Examples:
    - "Get all records from customers table"
    - "Query transactions table where amount greater than 1000"
    - "List users ordered by created_at"
    - "Show recent orders from orders table"

    Returns: List of matching records from the specified table.
    """
    args_schema: Type[BaseModel] = DatabaseQueryInput

    # Injected dependencies
    db_adapter: Optional[PostgreSQLAdapter] = None
    filter_generator: Optional[FilterGenerator] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        table: str,
        columns: Optional[str] = None,
        filters: Optional[str] = None,
        limit: int = 100,
        order_by: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(table, columns, filters, limit, order_by, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(table, columns, filters, limit, order_by, run_manager)
            )

    async def _arun(
        self,
        table: str,
        columns: Optional[str] = None,
        filters: Optional[str] = None,
        limit: int = 100,
        order_by: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute the tool asynchronously"""
        try:
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

                generated_filter = await self.filter_generator.generate_filters(filters)
                where_clause = generated_filter.sql_where_clause
                if where_clause:
                    where_clause = f"WHERE {where_clause}"

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
                {order_clause}
                LIMIT {limit}
            """.strip()

            logger.info(f"Executing query: {query}")

            # Execute query
            results = await self.db_adapter.query(query)

            # Format results
            return self._format_results(results, table)

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
        """Validate column list"""
        if columns == "*":
            return True
        # Split by comma and validate each column
        column_list = [col.strip() for col in columns.split(",")]
        return all(self._is_valid_identifier(col) for col in column_list)

    def _format_results(self, results: List[Dict], table: str) -> str:
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


class DatabaseAggregateTool(BaseTool):
    """
    Tool for performing aggregations on database tables
    Supports count, sum, average, max, min operations
    """

    name: str = "aggregate_database"
    description: str = """
    Perform aggregation operations on database tables.
    Use this for counting, summing, averaging, or finding min/max values.

    Examples:
    - "Count all cases in cases table"
    - "Sum total amount from transactions table"
    - "Average age from users table"
    - "Find maximum price in products table"
    - "Count orders grouped by status"

    Returns: Aggregated results based on the operation.
    """
    args_schema: Type[BaseModel] = DatabaseAggregateInput

    # Injected dependencies
    db_adapter: Optional[PostgreSQLAdapter] = None
    filter_generator: Optional[FilterGenerator] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        table: str,
        operation: str,
        column: Optional[str] = None,
        group_by: Optional[str] = None,
        filters: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(table, operation, column, group_by, filters, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(table, operation, column, group_by, filters, run_manager)
            )

    async def _arun(
        self,
        table: str,
        operation: str,
        column: Optional[str] = None,
        group_by: Optional[str] = None,
        filters: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute aggregation asynchronously"""
        try:
            if not self.db_adapter:
                return "Error: Database adapter not configured"

            # Validate inputs
            if not self._is_valid_identifier(table):
                return f"Error: Invalid table name"

            operation = operation.lower()
            valid_ops = ["count", "sum", "avg", "max", "min"]
            if operation not in valid_ops:
                return f"Error: Invalid operation. Must be one of: {', '.join(valid_ops)}"

            # Count doesn't need a column, others do
            if operation != "count":
                if not column:
                    return f"Error: Column required for {operation} operation"
                if not self._is_valid_identifier(column):
                    return f"Error: Invalid column name"

            # Build aggregation expression
            if operation == "count":
                agg_expr = "COUNT(*)"
            else:
                agg_expr = f"{operation.upper()}({column})"

            # Build SELECT clause
            if group_by:
                if not self._is_valid_identifier(group_by):
                    return f"Error: Invalid group_by column"
                select_clause = f"{group_by}, {agg_expr} as result"
            else:
                select_clause = f"{agg_expr} as result"

            # Build WHERE clause
            where_clause = ""
            if filters:
                if not self.filter_generator:
                    self.filter_generator = FilterGenerator()

                generated_filter = await self.filter_generator.generate_filters(filters)
                where_clause = generated_filter.sql_where_clause
                if where_clause:
                    where_clause = f"WHERE {where_clause}"

            # Build GROUP BY clause
            group_clause = f"GROUP BY {group_by}" if group_by else ""

            # Build complete query
            query = f"""
                SELECT {select_clause}
                FROM {table}
                {where_clause}
                {group_clause}
            """.strip()

            logger.info(f"Executing aggregation: {query}")

            # Execute query
            results = await self.db_adapter.query(query)

            # Format results
            return self._format_aggregation_results(results, operation, group_by)

        except Exception as e:
            logger.error(f"Database aggregation failed: {e}")
            return f"Error executing aggregation: {str(e)}"

    def _is_valid_identifier(self, identifier: str) -> bool:
        """Validate SQL identifier"""
        if not identifier:
            return False
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_\.]*$', identifier.strip()))

    def _format_aggregation_results(
        self,
        results: List[Dict],
        operation: str,
        group_by: Optional[str]
    ) -> str:
        """Format aggregation results"""
        if not results:
            return "No results from aggregation."

        if group_by:
            # Grouped results
            formatted = f"Aggregation results ({operation}):\n\n"
            for record in results:
                group_value = record.get(group_by, "Unknown")
                result_value = record.get("result", 0)
                formatted += f"- {group_by}={group_value}: {result_value}\n"
        else:
            # Single result
            result_value = results[0].get("result", 0)
            formatted = f"Result: {result_value}"

        return formatted
