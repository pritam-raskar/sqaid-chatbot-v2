"""
LangChain tool for filter generation
"""
from typing import Optional, Type, Any, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import json
import logging

from app.intelligence.filter_generator import FilterGenerator

logger = logging.getLogger(__name__)


class FilterGeneratorInput(BaseModel):
    """Input schema for filter generator tool"""
    query: str = Field(..., description="Natural language query describing desired filters")
    output_format: str = Field("sql", description="Output format: sql, api, or mongodb")
    table_name: Optional[str] = Field(None, description="Table name for SQL queries")


class FilterGeneratorTool(BaseTool):
    """
    Tool for converting natural language to database/API filters
    Generates filters in multiple formats (SQL, API params, MongoDB)
    """

    name: str = "generate_filters"
    description: str = """
    Convert natural language filter descriptions into executable filters.
    Use this when you need to create filters from user queries.

    Examples:
    - "Generate SQL filter for high priority cases from last week"
    - "Create API parameters for status is open and created today"
    - "Build MongoDB query for amount greater than 1000"
    - "Filter for pending requests assigned to John"

    Returns: Filter in specified format (SQL WHERE clause, API params, or MongoDB query).
    """
    args_schema: Type[BaseModel] = FilterGeneratorInput

    # Injected dependencies
    filter_generator: Optional[FilterGenerator] = None

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        query: str,
        output_format: str = "sql",
        table_name: Optional[str] = None,
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
                    self._arun(query, output_format, table_name, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(query, output_format, table_name, run_manager)
            )

    async def _arun(
        self,
        query: str,
        output_format: str = "sql",
        table_name: Optional[str] = None,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute filter generation asynchronously"""
        try:
            # Initialize filter generator if needed
            if not self.filter_generator:
                self.filter_generator = FilterGenerator()

            # Generate filters
            generated_filter = await self.filter_generator.generate_filters(
                query=query,
                schema=None,  # Could be enhanced with schema information
                context=None
            )

            # Format output based on requested format
            output_format = output_format.lower()

            if output_format == "sql":
                return self._format_sql_output(generated_filter, table_name)
            elif output_format == "api":
                return self._format_api_output(generated_filter)
            elif output_format == "mongodb":
                return self._format_mongodb_output(generated_filter)
            else:
                # Return all formats
                return self._format_all_formats(generated_filter, table_name)

        except Exception as e:
            logger.error(f"Filter generation failed: {e}")
            return f"Error generating filters: {str(e)}"

    def _format_sql_output(self, generated_filter, table_name: Optional[str]) -> str:
        """Format SQL WHERE clause output"""
        where_clause = generated_filter.sql_where_clause

        if not where_clause:
            return "No filters generated from query."

        output = "Generated SQL Filter:\n\n"

        if table_name:
            output += f"Full Query:\n"
            output += f"SELECT * FROM {table_name} WHERE {where_clause};\n\n"

        output += f"WHERE Clause:\n{where_clause}\n\n"
        output += f"Description: {generated_filter.description}"

        return output

    def _format_api_output(self, generated_filter) -> str:
        """Format API query parameters output"""
        api_params = generated_filter.api_query_params

        if not api_params:
            return "No API parameters generated from query."

        output = "Generated API Query Parameters:\n\n"
        output += json.dumps(api_params, indent=2)
        output += f"\n\nDescription: {generated_filter.description}"

        return output

    def _format_mongodb_output(self, generated_filter) -> str:
        """Format MongoDB query output"""
        mongo_query = generated_filter.mongodb_query

        if not mongo_query:
            return "No MongoDB query generated from query."

        output = "Generated MongoDB Query:\n\n"
        output += json.dumps(mongo_query, indent=2)
        output += f"\n\nDescription: {generated_filter.description}"

        return output

    def _format_all_formats(self, generated_filter, table_name: Optional[str]) -> str:
        """Format all filter formats"""
        output = "Generated Filters (All Formats):\n\n"

        # Description
        output += f"Description: {generated_filter.description}\n\n"

        # SQL
        output += "=== SQL Format ===\n"
        if table_name:
            output += f"SELECT * FROM {table_name} WHERE {generated_filter.sql_where_clause};\n\n"
        else:
            output += f"{generated_filter.sql_where_clause}\n\n"

        # API Parameters
        output += "=== API Parameters ===\n"
        output += json.dumps(generated_filter.api_query_params, indent=2)
        output += "\n\n"

        # MongoDB
        output += "=== MongoDB Query ===\n"
        output += json.dumps(generated_filter.mongodb_query, indent=2)
        output += "\n"

        return output
