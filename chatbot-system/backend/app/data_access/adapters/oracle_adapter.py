"""
Oracle Database Adapter using oracledb (python-oracledb)
"""
from typing import List, Dict, Any, Optional
import oracledb
import logging
from contextlib import asynccontextmanager

from app.data_access.base_adapter import BaseDataAdapter

logger = logging.getLogger(__name__)


class OracleAdapter(BaseDataAdapter):
    """
    Adapter for Oracle Database connections using python-oracledb
    Supports both thin (default) and thick modes
    """

    def __init__(
        self,
        user: str,
        password: str,
        dsn: str,
        mode: str = "thin",
        min_pool_size: int = 1,
        max_pool_size: int = 10,
        **kwargs
    ):
        """
        Initialize Oracle adapter

        Args:
            user: Oracle database username
            password: Oracle database password
            dsn: Data Source Name (host:port/service_name)
            mode: Connection mode ("thin" or "thick")
            min_pool_size: Minimum connections in pool
            max_pool_size: Maximum connections in pool
            **kwargs: Additional oracle parameters
        """
        super().__init__()
        self.user = user
        self.password = password
        self.dsn = dsn
        self.mode = mode
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.extra_params = kwargs
        self.pool = None

    async def connect(self) -> bool:
        """
        Establish connection pool to Oracle database

        Returns:
            True if connection successful
        """
        try:
            # Initialize thick mode if requested
            if self.mode == "thick":
                oracledb.init_oracle_client()

            # Create connection pool
            self.pool = oracledb.create_pool(
                user=self.user,
                password=self.password,
                dsn=self.dsn,
                min=self.min_pool_size,
                max=self.max_pool_size,
                **self.extra_params
            )

            logger.info(f"Oracle adapter connected to {self.dsn} ({self.mode} mode)")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Oracle: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Oracle connection pool"""
        if self.pool:
            self.pool.close()
            self.pool = None
            logger.info("Oracle adapter disconnected")

    async def query(self, sql: str, *params) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query

        Args:
            sql: SQL query string
            *params: Query parameters

        Returns:
            List of dictionaries representing rows
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    # Execute query
                    cursor.execute(sql, params if params else None)

                    # Get column names
                    columns = [col[0] for col in cursor.description]

                    # Fetch all results
                    rows = cursor.fetchall()

                    # Convert to list of dictionaries
                    return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Oracle query failed: {e}")
            raise

    async def query_one(self, sql: str, *params) -> Optional[Dict[str, Any]]:
        """
        Execute a query and return single row

        Args:
            sql: SQL query string
            *params: Query parameters

        Returns:
            Dictionary representing the row, or None
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params if params else None)

                    # Get column names
                    columns = [col[0] for col in cursor.description]

                    # Fetch one result
                    row = cursor.fetchone()

                    if row:
                        return dict(zip(columns, row))
                    return None

        except Exception as e:
            logger.error(f"Oracle query_one failed: {e}")
            raise

    async def execute(self, sql: str, *params) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE statement

        Args:
            sql: SQL statement
            *params: Statement parameters

        Returns:
            Number of rows affected
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params if params else None)
                    connection.commit()

                    return cursor.rowcount

        except Exception as e:
            logger.error(f"Oracle execute failed: {e}")
            raise

    async def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """
        Execute a statement multiple times with different parameters

        Args:
            sql: SQL statement
            params_list: List of parameter tuples

        Returns:
            Total number of rows affected
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.executemany(sql, params_list)
                    connection.commit()

                    return cursor.rowcount

        except Exception as e:
            logger.error(f"Oracle execute_many failed: {e}")
            raise

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for transactions

        Usage:
            async with adapter.transaction():
                await adapter.execute("INSERT ...")
                await adapter.execute("UPDATE ...")
        """
        connection = self.pool.acquire()
        try:
            yield connection
            connection.commit()
        except Exception as e:
            connection.rollback()
            logger.error(f"Oracle transaction failed, rolled back: {e}")
            raise
        finally:
            self.pool.release(connection)

    async def call_procedure(
        self,
        procedure_name: str,
        params: Optional[List] = None
    ) -> Any:
        """
        Call a stored procedure

        Args:
            procedure_name: Name of the stored procedure
            params: List of parameters

        Returns:
            Procedure result
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    if params:
                        result = cursor.callproc(procedure_name, params)
                    else:
                        result = cursor.callproc(procedure_name)

                    connection.commit()
                    return result

        except Exception as e:
            logger.error(f"Oracle procedure call failed: {e}")
            raise

    async def call_function(
        self,
        function_name: str,
        return_type: Any,
        params: Optional[List] = None
    ) -> Any:
        """
        Call a stored function

        Args:
            function_name: Name of the stored function
            return_type: Expected return type (e.g., oracledb.NUMBER, oracledb.STRING)
            params: List of parameters

        Returns:
            Function result
        """
        try:
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    result_var = cursor.var(return_type)

                    if params:
                        cursor.callfunc(function_name, return_type, params)
                    else:
                        cursor.callfunc(function_name, return_type)

                    return result_var.getvalue()

        except Exception as e:
            logger.error(f"Oracle function call failed: {e}")
            raise

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "adapter_type": "oracle",
            "dsn": self.dsn,
            "mode": self.mode,
            "pool_size": f"{self.min_pool_size}-{self.max_pool_size}",
            "connected": self.pool is not None
        }

    async def health_check(self) -> bool:
        """
        Check if the Oracle database connection is healthy

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try a simple query
            with self.pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
                    cursor.fetchone()
            return True
        except Exception as e:
            logger.error(f"Oracle health check failed: {e}")
            return False
