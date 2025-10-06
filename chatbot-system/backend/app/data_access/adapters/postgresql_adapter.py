"""
PostgreSQL Adapter for database operations.
Uses asyncpg for high-performance async database access.
"""

import asyncpg
import logging
import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from app.data_access.base_adapter import BaseDataAdapter

logger = logging.getLogger(__name__)


class PostgreSQLAdapter(BaseDataAdapter):
    """
    Adapter for PostgreSQL database operations.
    Provides connection pooling and query execution.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PostgreSQL adapter with configuration.

        Args:
            config: Configuration containing:
                - host: Database host
                - port: Database port
                - database: Database name
                - user: Username
                - password: Password
                - pool_size: Connection pool size
                - pool_min: Minimum connections in pool
                - pool_max: Maximum connections in pool
        """
        super().__init__(config)

        # Extract database configuration
        db_config = config.get('database', {}).get('postgresql', config)
        self.host = db_config.get('host', 'localhost')
        self.port = db_config.get('port', 5432)
        self.database = db_config.get('db') or db_config.get('database')
        self.user = db_config.get('user')
        self.password = db_config.get('password')

        # Pool configuration
        self.pool_min = db_config.get('pool_min', 5)
        self.pool_max = db_config.get('pool_max', 20)

        # Connection pool
        self.pool: Optional[asyncpg.Pool] = None

        # Schema metadata cache
        self.schema_metadata = {}
        self.prepared_statements = {}

        logger.info(f"Initialized PostgreSQL adapter for {self.host}:{self.port}/{self.database}")

    async def connect(self) -> None:
        """
        Establish connection to PostgreSQL database.

        Steps:
        1. Create connection pool
        2. Test connection
        3. Load schema metadata
        4. Prepare common queries
        """
        try:
            # Step 1: Create connection pool
            logger.info(f"Creating connection pool for PostgreSQL database...")
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.pool_min,
                max_size=self.pool_max,
                command_timeout=60
            )

            # Step 2: Test connection
            async with self.pool.acquire() as connection:
                version = await connection.fetchval('SELECT version()')
                logger.info(f"Connected to PostgreSQL: {version}")

            # Step 3: Load schema metadata
            await self._load_schema_metadata()

            # Step 4: Prepare common queries
            await self._prepare_common_queries()

            self.is_connected = True
            logger.info(f"Successfully connected to PostgreSQL database: {self.database}")

        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection pool and cleanup resources."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            self.is_connected = False
            logger.info(f"Disconnected from PostgreSQL database: {self.database}")

    async def execute_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of result dictionaries

        Steps:
        1. Get connection from pool
        2. Prepare statement
        3. Execute with parameters
        4. Fetch results
        5. Return formatted data
        6. Release connection
        """
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as connection:
            try:
                # Step 2 & 3: Prepare and execute query
                if params:
                    # Convert params to positional arguments for asyncpg
                    values = list(params.values())
                    # Replace named params with positional ($1, $2, etc.)
                    prepared_query = self._convert_to_positional(query, params)
                    rows = await connection.fetch(prepared_query, *values)
                else:
                    rows = await connection.fetch(query)

                # Step 4 & 5: Format results as dictionaries
                results = [dict(row) for row in rows]

                # Convert special types to JSON-serializable format
                for result in results:
                    for key, value in result.items():
                        if isinstance(value, datetime):
                            result[key] = value.isoformat()
                        elif isinstance(value, (dict, list)):
                            result[key] = json.dumps(value)

                logger.debug(f"Query returned {len(results)} rows")
                return results

            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Params: {params}")
                raise

    async def execute(self, operation: str, **kwargs) -> Any:
        """
        Execute a database operation.

        Args:
            operation: Operation type (query, insert, update, delete, transaction)
            **kwargs: Operation-specific parameters

        Returns:
            Operation result
        """
        if operation == 'query':
            return await self.execute_query(
                kwargs.get('query'),
                kwargs.get('params')
            )
        elif operation == 'insert':
            return await self._execute_insert(
                kwargs.get('table'),
                kwargs.get('data')
            )
        elif operation == 'update':
            return await self._execute_update(
                kwargs.get('table'),
                kwargs.get('data'),
                kwargs.get('where')
            )
        elif operation == 'delete':
            return await self._execute_delete(
                kwargs.get('table'),
                kwargs.get('where')
            )
        elif operation == 'transaction':
            return await self._execute_transaction(
                kwargs.get('operations')
            )
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    async def _execute_insert(self, table: str, data: Dict[str, Any]) -> Any:
        """Execute INSERT operation."""
        if not self.pool:
            await self.connect()

        columns = ', '.join(data.keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(data))])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"

        async with self.pool.acquire() as connection:
            try:
                row = await connection.fetchrow(query, *data.values())
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Insert failed: {e}")
                raise

    async def _execute_update(self, table: str, data: Dict[str, Any], where: Dict[str, Any]) -> int:
        """Execute UPDATE operation."""
        if not self.pool:
            await self.connect()

        set_clause = ', '.join([f"{k} = ${i+1}" for i, k in enumerate(data.keys())])
        where_clause = ' AND '.join([f"{k} = ${i+len(data)+1}" for i, k in enumerate(where.keys())])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

        values = list(data.values()) + list(where.values())

        async with self.pool.acquire() as connection:
            try:
                result = await connection.execute(query, *values)
                # Extract number of affected rows from result string
                affected = int(result.split()[-1]) if result else 0
                return affected
            except Exception as e:
                logger.error(f"Update failed: {e}")
                raise

    async def _execute_delete(self, table: str, where: Dict[str, Any]) -> int:
        """Execute DELETE operation."""
        if not self.pool:
            await self.connect()

        where_clause = ' AND '.join([f"{k} = ${i+1}" for i, k in enumerate(where.keys())])
        query = f"DELETE FROM {table} WHERE {where_clause}"

        async with self.pool.acquire() as connection:
            try:
                result = await connection.execute(query, *where.values())
                # Extract number of affected rows from result string
                affected = int(result.split()[-1]) if result else 0
                return affected
            except Exception as e:
                logger.error(f"Delete failed: {e}")
                raise

    async def _execute_transaction(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """Execute multiple operations in a transaction."""
        if not self.pool:
            await self.connect()

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                results = []
                for op in operations:
                    op_type = op.get('type')
                    if op_type == 'query':
                        result = await connection.fetch(op.get('query'), *op.get('params', []))
                        results.append([dict(row) for row in result])
                    elif op_type == 'execute':
                        result = await connection.execute(op.get('query'), *op.get('params', []))
                        results.append(result)
                    else:
                        raise ValueError(f"Unknown operation type in transaction: {op_type}")
                return results

    async def _load_schema_metadata(self):
        """Load database schema metadata."""
        if not self.pool:
            return

        async with self.pool.acquire() as connection:
            # Get table information
            tables = await connection.fetch("""
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)

            for table in tables:
                table_name = table['table_name']

                # Get column information
                columns = await connection.fetch("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                """, table_name)

                self.schema_metadata[table_name] = {
                    'type': table['table_type'],
                    'columns': [dict(col) for col in columns]
                }

            logger.info(f"Loaded metadata for {len(self.schema_metadata)} tables")

    async def _prepare_common_queries(self):
        """Prepare commonly used queries for better performance."""
        # This can be extended based on application needs
        pass

    def _convert_to_positional(self, query: str, params: Dict[str, Any]) -> str:
        """
        Convert named parameters to positional parameters for asyncpg.

        Args:
            query: Query with named parameters (:param_name)
            params: Parameter dictionary

        Returns:
            Query with positional parameters ($1, $2, etc.)
        """
        converted_query = query
        for i, param_name in enumerate(params.keys(), 1):
            converted_query = converted_query.replace(f':{param_name}', f'${i}')
        return converted_query

    async def health_check(self) -> bool:
        """
        Check if the database is accessible and healthy.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            if not self.pool:
                return False

            async with self.pool.acquire() as connection:
                result = await connection.fetchval('SELECT 1')
                return result == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Table metadata dictionary or None
        """
        return self.schema_metadata.get(table_name)