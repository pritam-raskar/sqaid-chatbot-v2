"""
LangChain tools for case/ticket queries
"""
from typing import Optional, Type, Any, Dict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import json
import logging

from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter
from app.data_access.adapters.rest_adapter import RESTAdapter

logger = logging.getLogger(__name__)


class CaseQueryInput(BaseModel):
    """Input schema for case query tool"""
    status: Optional[str] = Field(None, description="Filter by status (open, closed, pending)")
    priority: Optional[str] = Field(None, description="Filter by priority (high, medium, low)")
    assigned_to: Optional[str] = Field(None, description="Filter by assigned agent")
    date_range: Optional[str] = Field(None, description="Date range (today, this_week, this_month)")
    limit: Optional[int] = Field(10, description="Maximum number of results")


class CaseDetailInput(BaseModel):
    """Input schema for case detail tool"""
    case_id: str = Field(..., description="Case ID to retrieve")


class CaseQueryTool(BaseTool):
    """
    Tool for querying cases with filters
    Automatically routes to appropriate data source (PostgreSQL or REST API)
    """

    name: str = "query_cases"
    description: str = """
    Query cases from the case management system with optional filters.
    Use this when user asks about multiple cases, case lists, or case statistics.

    Examples:
    - "Show me all open cases"
    - "What are the high priority cases?"
    - "List cases assigned to me"
    - "How many cases were opened this week?"

    Returns a list of cases matching the filters.
    """
    args_schema: Type[BaseModel] = CaseQueryInput

    # Injected dependencies
    db_adapter: Optional[PostgreSQLAdapter] = None
    api_adapter: Optional[RESTAdapter] = None
    prefer_source: str = "database"  # "database" or "api"

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date_range: Optional[str] = None,
        limit: int = 10,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution - runs async version"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create new loop in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._arun(status, priority, assigned_to, date_range, limit, run_manager)
                )
                return future.result()
        else:
            return loop.run_until_complete(
                self._arun(status, priority, assigned_to, date_range, limit, run_manager)
            )

    async def _arun(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        date_range: Optional[str] = None,
        limit: int = 10,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute the tool asynchronously"""
        try:
            # Build query based on preferred source
            if self.prefer_source == "database" and self.db_adapter:
                results = await self._query_database(status, priority, assigned_to, date_range, limit)
            elif self.api_adapter:
                results = await self._query_api(status, priority, assigned_to, date_range, limit)
            else:
                return "Error: No data source available"

            # Format results
            return self._format_results(results)

        except Exception as e:
            logger.error(f"Case query failed: {e}")
            return f"Error querying cases: {str(e)}"

    async def _query_database(
        self,
        status: Optional[str],
        priority: Optional[str],
        assigned_to: Optional[str],
        date_range: Optional[str],
        limit: int
    ) -> list:
        """Query cases from PostgreSQL database"""
        # Build SQL query
        conditions = []
        params = []
        param_counter = 1

        if status:
            conditions.append(f"status = ${param_counter}")
            params.append(status)
            param_counter += 1

        if priority:
            conditions.append(f"priority = ${param_counter}")
            params.append(priority)
            param_counter += 1

        if assigned_to:
            conditions.append(f"assigned_to = ${param_counter}")
            params.append(assigned_to)
            param_counter += 1

        if date_range:
            date_filter = self._convert_date_range(date_range)
            conditions.append(f"created_at >= ${param_counter}")
            params.append(date_filter)
            param_counter += 1

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"""
            SELECT id, title, status, priority, assigned_to, created_at, updated_at
            FROM cases
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_counter}
        """
        params.append(limit)

        results = await self.db_adapter.query(query, *params)
        return results

    async def _query_api(
        self,
        status: Optional[str],
        priority: Optional[str],
        assigned_to: Optional[str],
        date_range: Optional[str],
        limit: int
    ) -> list:
        """Query cases from REST API"""
        # Build query parameters
        params = {"limit": limit}

        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        if assigned_to:
            params["assigned_to"] = assigned_to
        if date_range:
            params["date_range"] = date_range

        response = await self.api_adapter.get("/api/cases", params=params)
        return response.get("cases", [])

    def _convert_date_range(self, date_range: str) -> str:
        """Convert date range string to ISO date"""
        from datetime import datetime, timedelta

        now = datetime.now()
        if date_range == "today":
            return now.date().isoformat()
        elif date_range == "this_week":
            start_of_week = now - timedelta(days=now.weekday())
            return start_of_week.date().isoformat()
        elif date_range == "this_month":
            return now.replace(day=1).date().isoformat()
        else:
            return now.date().isoformat()

    def _format_results(self, results: list) -> str:
        """Format query results for LLM consumption"""
        if not results:
            return "No cases found matching the criteria."

        formatted = f"Found {len(results)} case(s):\n\n"

        for i, case in enumerate(results, 1):
            formatted += f"{i}. Case #{case.get('id', 'N/A')}\n"
            formatted += f"   Title: {case.get('title', 'N/A')}\n"
            formatted += f"   Status: {case.get('status', 'N/A')}\n"
            formatted += f"   Priority: {case.get('priority', 'N/A')}\n"
            formatted += f"   Assigned to: {case.get('assigned_to', 'Unassigned')}\n"
            formatted += f"   Created: {case.get('created_at', 'N/A')}\n\n"

        return formatted


class CaseDetailTool(BaseTool):
    """
    Tool for retrieving detailed information about a specific case
    """

    name: str = "get_case_details"
    description: str = """
    Retrieve detailed information about a specific case by ID.
    Use this when user asks about a specific case number.

    Examples:
    - "What is the status of case #12345?"
    - "Show me details for case 67890"
    - "Tell me about ticket #555"

    Returns complete case information including timeline, attachments, and comments.
    """
    args_schema: Type[BaseModel] = CaseDetailInput

    # Injected dependencies
    db_adapter: Optional[PostgreSQLAdapter] = None
    api_adapter: Optional[RESTAdapter] = None
    prefer_source: str = "database"

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        case_id: str,
        run_manager: Optional[Any] = None
    ) -> str:
        """Synchronous execution"""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._arun(case_id, run_manager))
                return future.result()
        else:
            return loop.run_until_complete(self._arun(case_id, run_manager))

    async def _arun(
        self,
        case_id: str,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute the tool asynchronously"""
        try:
            # Retrieve case details
            if self.prefer_source == "database" and self.db_adapter:
                case_data = await self._get_from_database(case_id)
            elif self.api_adapter:
                case_data = await self._get_from_api(case_id)
            else:
                return "Error: No data source available"

            if not case_data:
                return f"Case #{case_id} not found."

            # Format case details
            return self._format_case_details(case_data)

        except Exception as e:
            logger.error(f"Case detail retrieval failed: {e}")
            return f"Error retrieving case details: {str(e)}"

    async def _get_from_database(self, case_id: str) -> Optional[Dict]:
        """Get case from database"""
        query = """
            SELECT id, title, description, status, priority, assigned_to,
                   customer_id, created_at, updated_at, closed_at
            FROM cases
            WHERE id = $1
        """

        result = await self.db_adapter.query_one(query, int(case_id))
        return dict(result) if result else None

    async def _get_from_api(self, case_id: str) -> Optional[Dict]:
        """Get case from REST API"""
        response = await self.api_adapter.get(f"/api/cases/{case_id}")
        return response.get("case")

    def _format_case_details(self, case_data: Dict) -> str:
        """Format case details for LLM"""
        formatted = f"Case #{case_data.get('id')} Details:\n\n"
        formatted += f"Title: {case_data.get('title', 'N/A')}\n"
        formatted += f"Status: {case_data.get('status', 'N/A')}\n"
        formatted += f"Priority: {case_data.get('priority', 'N/A')}\n"
        formatted += f"Description: {case_data.get('description', 'N/A')}\n\n"
        formatted += f"Assigned to: {case_data.get('assigned_to', 'Unassigned')}\n"
        formatted += f"Customer ID: {case_data.get('customer_id', 'N/A')}\n\n"
        formatted += f"Created: {case_data.get('created_at', 'N/A')}\n"
        formatted += f"Last Updated: {case_data.get('updated_at', 'N/A')}\n"

        if case_data.get('closed_at'):
            formatted += f"Closed: {case_data['closed_at']}\n"

        return formatted
