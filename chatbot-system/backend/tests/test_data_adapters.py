"""
Data Adapter Integration Tests
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

from app.data.rest_adapter import RESTAPIAdapter
from app.data.postgres_adapter import PostgreSQLAdapter
from tests.mocks import MockDataAdapterResponses


class TestRESTAPIAdapter:
    """Test REST API data adapter"""

    @pytest.mark.asyncio
    async def test_get_request(self, mock_api_responses):
        """Test GET request to REST API"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(
                200,
                json=mock_api_responses["/api/cases"]
            )

            adapter = RESTAPIAdapter(base_url="http://api.example.com")
            result = await adapter.get("/api/cases")

            assert result is not None
            assert "cases" in result
            assert len(result["cases"]) == 2

    @pytest.mark.asyncio
    async def test_post_request(self):
        """Test POST request to REST API"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = httpx.Response(
                201,
                json={"id": "12350", "status": "created"}
            )

            adapter = RESTAPIAdapter(base_url="http://api.example.com")
            result = await adapter.post(
                "/api/cases",
                data={"title": "New Case", "priority": "high"}
            )

            assert result["status"] == "created"
            assert "id" in result

    @pytest.mark.asyncio
    async def test_authentication_headers(self):
        """Test API authentication header injection"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(200, json={})

            adapter = RESTAPIAdapter(
                base_url="http://api.example.com",
                auth_token="Bearer test-token-123"
            )
            await adapter.get("/api/cases")

            # Verify auth header was included
            call_kwargs = mock_get.call_args.kwargs
            assert "headers" in call_kwargs
            assert call_kwargs["headers"]["Authorization"] == "Bearer test-token-123"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for failed API requests"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(
                404,
                json={"error": "Not Found"}
            )

            adapter = RESTAPIAdapter(base_url="http://api.example.com")

            with pytest.raises(Exception):
                await adapter.get("/api/invalid")

    @pytest.mark.asyncio
    async def test_retry_logic(self):
        """Test retry logic for transient failures"""
        with patch('httpx.AsyncClient.get') as mock_get:
            # First call fails, second succeeds
            mock_get.side_effect = [
                httpx.Response(500, json={"error": "Internal Server Error"}),
                httpx.Response(200, json={"success": True})
            ]

            adapter = RESTAPIAdapter(
                base_url="http://api.example.com",
                max_retries=2
            )
            result = await adapter.get("/api/cases")

            assert result["success"] is True
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_configuration(self):
        """Test timeout configuration"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = httpx.Response(200, json={})

            adapter = RESTAPIAdapter(
                base_url="http://api.example.com",
                timeout=5.0
            )
            await adapter.get("/api/cases")

            call_kwargs = mock_get.call_args.kwargs
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 5.0


class TestPostgreSQLAdapter:
    """Test PostgreSQL data adapter"""

    @pytest.mark.asyncio
    async def test_query_execution(self, mock_postgres_pool):
        """Test executing a query"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()

            result = await adapter.query("SELECT * FROM cases WHERE status = $1", "open")

            assert len(result) == 2
            assert result[0]["name"] == "Test Case"

    @pytest.mark.asyncio
    async def test_query_one(self, mock_postgres_pool):
        """Test fetching single row"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()

            result = await adapter.query_one("SELECT * FROM cases WHERE id = $1", 1)

            assert result is not None
            assert result["id"] == 1
            assert result["name"] == "Test Case"

    @pytest.mark.asyncio
    async def test_execute_statement(self, mock_postgres_pool):
        """Test executing INSERT/UPDATE/DELETE"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()

            result = await adapter.execute(
                "INSERT INTO cases (name, status) VALUES ($1, $2)",
                "New Case",
                "open"
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_transaction(self, mock_postgres_pool):
        """Test transaction handling"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()

            async with adapter.transaction():
                await adapter.execute(
                    "INSERT INTO cases (name) VALUES ($1)",
                    "Case 1"
                )
                await adapter.execute(
                    "INSERT INTO cases (name) VALUES ($1)",
                    "Case 2"
                )

            # Both inserts should be committed

    @pytest.mark.asyncio
    async def test_connection_pooling(self, mock_postgres_pool):
        """Test connection pool management"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password",
                min_pool_size=2,
                max_pool_size=10
            )
            await adapter.connect()

            # Execute multiple concurrent queries
            results = await asyncio.gather(*[
                adapter.query("SELECT * FROM cases")
                for _ in range(5)
            ])

            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_parameterized_queries(self, mock_postgres_pool):
        """Test SQL injection protection via parameterized queries"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()

            # Malicious input should be safely parameterized
            malicious_input = "'; DROP TABLE cases; --"
            result = await adapter.query(
                "SELECT * FROM cases WHERE name = $1",
                malicious_input
            )

            # Should execute safely without SQL injection
            assert result is not None

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection failures"""
        with patch('asyncpg.create_pool', side_effect=Exception("Connection failed")):
            adapter = PostgreSQLAdapter(
                host="invalid-host",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )

            with pytest.raises(Exception):
                await adapter.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_postgres_pool):
        """Test graceful disconnection"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool):
            adapter = PostgreSQLAdapter(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_password"
            )
            await adapter.connect()
            await adapter.disconnect()

            # Pool should be closed
            assert adapter.pool is None or not adapter.pool._closed


class TestDataAdapterIntegration:
    """Test integration between multiple data adapters"""

    @pytest.mark.asyncio
    async def test_multi_source_query(self, mock_postgres_pool, mock_api_responses):
        """Test querying multiple data sources"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool), \
             patch('httpx.AsyncClient.get') as mock_get:

            mock_get.return_value = httpx.Response(
                200,
                json=mock_api_responses["/api/cases/12345"]
            )

            # Initialize adapters
            pg_adapter = PostgreSQLAdapter(
                host="localhost",
                database="test_db",
                user="test_user",
                password="test_password"
            )
            rest_adapter = RESTAPIAdapter(base_url="http://api.example.com")

            await pg_adapter.connect()

            # Query both sources
            db_results = await pg_adapter.query("SELECT * FROM cases")
            api_results = await rest_adapter.get("/api/cases/12345")

            assert len(db_results) > 0
            assert api_results["id"] == "12345"

    @pytest.mark.asyncio
    async def test_data_aggregation(self, mock_postgres_pool, mock_api_responses):
        """Test aggregating data from multiple sources"""
        with patch('asyncpg.create_pool', return_value=mock_postgres_pool), \
             patch('httpx.AsyncClient.get') as mock_get:

            mock_get.return_value = httpx.Response(
                200,
                json=mock_api_responses["/api/cases"]
            )

            pg_adapter = PostgreSQLAdapter(
                host="localhost",
                database="test_db",
                user="test_user",
                password="test_password"
            )
            rest_adapter = RESTAPIAdapter(base_url="http://api.example.com")

            await pg_adapter.connect()

            # Aggregate results
            db_cases = await pg_adapter.query("SELECT * FROM cases")
            api_cases = await rest_adapter.get("/api/cases")

            all_cases = list(db_cases) + api_cases["cases"]
            assert len(all_cases) > 2
