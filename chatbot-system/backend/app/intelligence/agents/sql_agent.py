"""
SQL Agent - Converts natural language to SQL using LangChain SQL Agent.
Leverages existing PostgreSQL tools and database connections.
"""
from typing import Dict, Any, Optional, List
import logging
import json
import re

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from sqlalchemy import create_engine

from app.intelligence.agents.base_agent import BaseAgent
from app.intelligence.orchestration.types import AgentType, DataSourceType
from app.intelligence.tool_registry import ToolRegistry
from app.llm.base_provider import BaseLLMProvider
from app.data_access.adapters.postgresql_adapter import PostgreSQLAdapter

logger = logging.getLogger(__name__)


class SQLAgent(BaseAgent):
    """
    Specialized agent for Natural Language to SQL conversion.

    Capabilities:
    - Understands database schema automatically
    - Generates SQL from natural language
    - Executes queries safely (read-only)
    - Handles complex queries (JOINs, GROUP BY, aggregations)
    - Validates and fixes SQL errors

    Architecture:
        User Query → LangChain SQL Agent → SQL Generation →
        PostgreSQL Adapter → Results → Format → Return

    Example Queries:
        - "How many alerts do we have?"
        - "Show me all alerts for users in Engineering department"
        - "Count alerts by type"
        - "What are the top 5 alert types?"
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        db_adapter: PostgreSQLAdapter,
        schema_name: str = "info_alert"
    ):
        """
        Initialize SQL Agent.

        Args:
            llm_provider: LLM for SQL generation
            tool_registry: Registry with database tools
            db_adapter: PostgreSQL adapter instance
            schema_name: Default schema for queries

        Steps:
            1. Initialize base agent with SQL data source filter
            2. Create SQLAlchemy engine from adapter config
            3. Initialize LangChain SQLDatabase
            4. Create SQL Agent with toolkit
        """
        # Initialize base agent with PostgreSQL filter
        super().__init__(
            agent_type=AgentType.SQL_AGENT,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            data_source_filter=DataSourceType.POSTGRESQL
        )

        self.db_adapter = db_adapter
        self.schema_name = schema_name
        self.last_sql = None  # Track last generated SQL
        self.last_tool_used = None

        logger.info(f"🔧 Initializing SQLAgent with schema '{schema_name}'...")

        # Create SQLAlchemy engine from adapter config
        self.engine = self._create_sqlalchemy_engine()

        # Initialize LangChain SQLDatabase
        logger.info(f"📊 Creating LangChain SQLDatabase...")
        self.sql_database = SQLDatabase(
            engine=self.engine,
            schema=schema_name,
            view_support=True,
            sample_rows_in_table_info=3
        )

        # Create LangChain LLM wrapper
        logger.info(f"🤖 Creating LangChain LLM wrapper...")
        self.langchain_llm = self._create_langchain_llm()

        # Create SQL Agent Toolkit
        logger.info(f"🛠️ Creating SQL Agent Toolkit...")
        self.toolkit = SQLDatabaseToolkit(
            db=self.sql_database,
            llm=self.langchain_llm
        )

        # Create SQL Agent
        logger.info(f"🎯 Creating SQL Agent...")
        self.sql_agent = create_sql_agent(
            llm=self.langchain_llm,
            toolkit=self.toolkit,
            agent_type="tool-calling",  # Latest recommended type
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
            max_execution_time=30
        )

        logger.info(
            f"✅ SQLAgent initialized with schema '{schema_name}', "
            f"{len(self.tools)} database tools available"
        )

    def _create_sqlalchemy_engine(self):
        """
        Create SQLAlchemy engine from PostgreSQL adapter config.

        Returns:
            SQLAlchemy Engine instance

        Connection String Format:
            postgresql://user:password@host:port/database
        """
        config = self.db_adapter
        conn_string = (
            f"postgresql://{config.user}:{config.password}@"
            f"{config.host}:{config.port}/{config.database}"
        )

        engine = create_engine(
            conn_string,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set True for SQL debug logging
        )

        logger.debug(f"🔗 Created SQLAlchemy engine for {config.host}/{config.database}")
        return engine

    def _create_langchain_llm(self):
        """
        Create LangChain-compatible LLM wrapper from BaseLLMProvider.

        This bridges our provider-agnostic BaseLLMProvider with
        LangChain's expected interface.

        Returns:
            LangChain LLM instance
        """
        # Import based on actual provider type
        provider_name = self.llm_provider.__class__.__name__.lower()

        logger.debug(f"Creating LangChain LLM for provider: {provider_name}")

        if "anthropic" in provider_name:
            from langchain_anthropic import ChatAnthropic
            # Use the API key from existing provider
            return ChatAnthropic(
                model_name=getattr(self.llm_provider, 'model', 'claude-3-5-haiku-20241022'),
                temperature=0,  # Deterministic for SQL generation
                anthropic_api_key=getattr(self.llm_provider, 'api_key', None)
            )
        elif "openai" in provider_name:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model_name=getattr(self.llm_provider, 'model', 'gpt-4'),
                temperature=0,
                api_key=getattr(self.llm_provider, 'api_key', None)
            )
        elif "litellm" in provider_name:
            # LiteLLM supports multiple backends (OpenAI, Azure, etc.)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model_name=getattr(self.llm_provider, 'model', 'gpt-4'),
                temperature=0,
                api_key=getattr(self.llm_provider, 'api_key', None),
                base_url=getattr(self.llm_provider, 'base_url', None)
            )
        elif "eliza" in provider_name:
            # Eliza is enterprise LLM - use OpenAI compatible wrapper
            from langchain_openai import ChatOpenAI
            logger.info("🔧 Using OpenAI-compatible wrapper for Eliza")
            return ChatOpenAI(
                model_name=getattr(self.llm_provider, 'model', getattr(self.llm_provider, 'default_model', 'llama-3.3')),
                temperature=0,
                # Eliza doesn't use API keys in the same way, it uses certificates
                # The provider handles authentication, so we can use a placeholder
                api_key="eliza-internal"
            )
        else:
            # Fallback - try OpenAI compatible wrapper
            logger.warning(f"⚠️ Unknown provider: {provider_name}, trying OpenAI-compatible wrapper")
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model_name=getattr(self.llm_provider, 'model', 'gpt-4'),
                temperature=0
            )

    async def _execute_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> Any:
        """
        Execute natural language query by converting to SQL.

        Args:
            query: Natural language question
            context: Additional context (previous results, filters, etc.)
            parameters: Optional parameters (table hints, limits, etc.)

        Returns:
            Query results as list of dicts

        Flow:
            1. Build context-enriched prompt
            2. Call LangChain SQL Agent
            3. Agent generates SQL
            4. Agent executes SQL
            5. Agent returns results
            6. Format and return

        Example:
            query: "How many alerts are there?"
            → SQL: "SELECT COUNT(*) as count FROM info_alert.cm_alerts"
            → Result: [{"count": 29}]
        """
        logger.info(f"🔍 [SQLAgent] Processing: {query[:100]}...")

        # Build enriched prompt with context
        enriched_query = self._build_enriched_query(query, context, parameters)
        logger.debug(f"📝 Enriched query: {enriched_query}")

        try:
            # Invoke SQL Agent (this generates and executes SQL)
            logger.info(f"⚙️ Invoking SQL Agent...")
            result = await self.sql_agent.ainvoke({"input": enriched_query})

            # Extract output
            output = result.get("output", "")
            logger.debug(f"📤 Agent output: {output[:200]}...")

            # Try to parse result
            parsed_result = self._parse_agent_output(output)

            # Track SQL used (for debugging/logging)
            self.last_sql = self._extract_sql_from_result(result)
            self.last_tool_used = "langchain_sql_agent"

            logger.info(f"✅ [SQLAgent] SQL executed successfully, {len(parsed_result)} results")
            if self.last_sql:
                logger.debug(f"💾 SQL: {self.last_sql}")

            return parsed_result

        except Exception as e:
            logger.error(f"❌ [SQLAgent] Execution failed: {e}", exc_info=True)

            # Fallback: Try using existing database tools directly
            logger.warning(f"🔄 Attempting fallback to simple query...")
            return await self._fallback_to_simple_query(query, parameters)

    def _build_enriched_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build enriched query with context and parameters.

        Args:
            query: Base natural language query
            context: Additional context
            parameters: Query parameters

        Returns:
            Enriched query string

        Example:
            Input: query="Count alerts", context={"user_filter": "Engineering"}
            Output: "Count alerts for users in Engineering department"
        """
        enriched = query

        # Add context hints
        if context:
            if "filters" in context:
                enriched += f" (Filters: {context['filters']})"

            if "previous_results" in context:
                enriched += f" (Based on previous query results)"

        # Add parameter hints
        if parameters:
            if "limit" in parameters:
                enriched += f" (Limit results to {parameters['limit']})"

            if "table_hint" in parameters:
                enriched += f" (Use table: {parameters['table_hint']})"

        return enriched

    def _parse_agent_output(self, output: str) -> List[Dict[str, Any]]:
        """
        Parse SQL Agent output into structured format.

        Args:
            output: Raw output from SQL Agent

        Returns:
            List of result dicts

        The SQL Agent returns results in various formats:
        - "The query returned 29 rows" → [{"count": 29}]
        - Actual data rows
        - Error messages
        """
        # Try to extract JSON
        try:
            # Look for JSON array
            json_match = re.search(r'\[.*\]', output, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                logger.debug(f"✅ Parsed JSON array with {len(parsed)} items")
                return parsed

            # Look for JSON object
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                parsed = [json.loads(json_match.group())]
                logger.debug(f"✅ Parsed JSON object")
                return parsed

        except json.JSONDecodeError as e:
            logger.debug(f"⚠️ JSON parsing failed: {e}")

        # Try to extract count from text
        count_match = re.search(r'(\d+)\s+(rows?|results?|records?)', output, re.IGNORECASE)
        if count_match:
            count = int(count_match.group(1))
            logger.debug(f"✅ Extracted count: {count}")
            return [{"count": count}]

        # Return raw output as text
        logger.debug(f"⚠️ Returning raw output as text")
        return [{"result": output}]

    def _extract_sql_from_result(self, result: Dict) -> Optional[str]:
        """
        Extract generated SQL from agent result for debugging.

        Args:
            result: Full agent result dict

        Returns:
            SQL string or None
        """
        # Check intermediate steps
        if "intermediate_steps" in result:
            for step in result["intermediate_steps"]:
                if isinstance(step, tuple) and len(step) > 0:
                    action = step[0]
                    if hasattr(action, 'tool_input'):
                        if isinstance(action.tool_input, dict):
                            if 'query' in action.tool_input:
                                return action.tool_input['query']

        return None

    async def _fallback_to_simple_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Use existing database tools directly if SQL agent fails.

        Args:
            query: Natural language query
            parameters: Query parameters

        Returns:
            Query results

        This uses the existing PostgreSQL tools from the tool registry
        as a fallback when LangChain SQL Agent fails.
        """
        logger.warning("🔄 [SQLAgent] Falling back to simple query execution")

        # Try to use an existing database tool
        for tool_name, tool in self.tools.items():
            if "cm_alerts" in tool_name.lower():
                try:
                    logger.info(f"🔧 Trying fallback tool: {tool_name}")
                    # Execute tool with basic parameters
                    result = await tool._arun(
                        columns="COUNT(*) as count",
                        filters=""
                    )
                    logger.info(f"✅ Fallback succeeded with {tool_name}")
                    return [{"count": result}]
                except Exception as e:
                    logger.error(f"❌ Fallback tool execution failed: {e}")

        logger.error(f"❌ All fallback attempts failed")
        return [{"error": "Query execution failed"}]

    def _get_tool_name_used(self) -> Optional[str]:
        """Override to return the actual tool name used"""
        return self.last_tool_used

    def get_last_sql(self) -> Optional[str]:
        """Get the last SQL query that was generated and executed"""
        return self.last_sql

    def get_table_info(self) -> str:
        """Get information about available database tables"""
        return self.sql_database.get_table_info()

    def get_usable_table_names(self) -> List[str]:
        """Get list of table names the agent can query"""
        return self.sql_database.get_usable_table_names()
