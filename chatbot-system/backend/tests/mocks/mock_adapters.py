"""Mock Data Adapters for testing"""
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from app.data_access.base_adapter import BaseAdapter


class MockPostgreSQLAdapter(BaseAdapter):
    """Mock PostgreSQL adapter for testing"""

    def __init__(self, responses: Optional[List[Dict]] = None, should_fail: bool = False):
        super().__init__()
        self.responses = responses or [
            {"id": 1, "name": "Test Case", "status": "Open"},
            {"id": 2, "name": "Another Case", "status": "Closed"}
        ]
        self.should_fail = should_fail
        self.query_history = []
        self._is_connected = False

    async def connect(self) -> bool:
        """Mock connection"""
        if self.should_fail:
            return False
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False

    async def query(self, sql: str, *params) -> List[Dict[str, Any]]:
        """Mock query execution"""
        if self.should_fail:
            raise Exception("Mock PostgreSQL query failure")

        self.query_history.append({"sql": sql, "params": params})
        return self.responses

    async def query_one(self, sql: str, *params) -> Optional[Dict[str, Any]]:
        """Mock single row query"""
        if self.should_fail:
            raise Exception("Mock PostgreSQL query_one failure")

        self.query_history.append({"sql": sql, "params": params})
        return self.responses[0] if self.responses else None

    async def execute(self, sql: str, *params) -> int:
        """Mock execute"""
        if self.should_fail:
            raise Exception("Mock PostgreSQL execute failure")

        self.query_history.append({"sql": sql, "params": params})
        return 1

    async def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """Mock execute many"""
        if self.should_fail:
            raise Exception("Mock PostgreSQL execute_many failure")

        self.query_history.append({"sql": sql, "params_list": params_list})
        return len(params_list)

    @asynccontextmanager
    async def transaction(self):
        """Mock transaction context"""
        yield self

    def get_connection_info(self) -> Dict[str, Any]:
        """Get mock connection info"""
        return {
            "adapter_type": "mock_postgresql",
            "connected": self._is_connected,
            "query_count": len(self.query_history)
        }


class MockOracleAdapter(BaseAdapter):
    """Mock Oracle adapter for testing"""

    def __init__(self, responses: Optional[List[Dict]] = None, should_fail: bool = False):
        super().__init__()
        self.responses = responses or [
            {"CASE_ID": 101, "CASE_NAME": "Oracle Case", "STATUS": "PENDING"},
            {"CASE_ID": 102, "CASE_NAME": "Another Oracle Case", "STATUS": "RESOLVED"}
        ]
        self.should_fail = should_fail
        self.query_history = []
        self._is_connected = False

    async def connect(self) -> bool:
        """Mock connection"""
        if self.should_fail:
            return False
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False

    async def query(self, sql: str, *params) -> List[Dict[str, Any]]:
        """Mock query execution"""
        if self.should_fail:
            raise Exception("Mock Oracle query failure")

        self.query_history.append({"sql": sql, "params": params})
        return self.responses

    async def query_one(self, sql: str, *params) -> Optional[Dict[str, Any]]:
        """Mock single row query"""
        if self.should_fail:
            raise Exception("Mock Oracle query_one failure")

        self.query_history.append({"sql": sql, "params": params})
        return self.responses[0] if self.responses else None

    async def execute(self, sql: str, *params) -> int:
        """Mock execute"""
        if self.should_fail:
            raise Exception("Mock Oracle execute failure")

        self.query_history.append({"sql": sql, "params": params})
        return 1

    def get_connection_info(self) -> Dict[str, Any]:
        """Get mock connection info"""
        return {
            "adapter_type": "mock_oracle",
            "connected": self._is_connected,
            "query_count": len(self.query_history)
        }


class MockRESTAdapter(BaseAdapter):
    """Mock REST API adapter for testing"""

    def __init__(self, responses: Optional[Dict] = None, should_fail: bool = False):
        super().__init__()
        self.responses = responses or {
            "cases": [
                {"id": "rest-1", "title": "REST Case 1", "priority": "High"},
                {"id": "rest-2", "title": "REST Case 2", "priority": "Medium"}
            ]
        }
        self.should_fail = should_fail
        self.request_history = []
        self._is_connected = False

    async def connect(self) -> bool:
        """Mock connection"""
        if self.should_fail:
            return False
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Mock GET request"""
        if self.should_fail:
            raise Exception("Mock REST GET failure")

        self.request_history.append({
            "method": "GET",
            "endpoint": endpoint,
            "params": params
        })
        return self.responses

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock POST request"""
        if self.should_fail:
            raise Exception("Mock REST POST failure")

        self.request_history.append({
            "method": "POST",
            "endpoint": endpoint,
            "data": data
        })
        return {"status": "success", "id": "new-rest-item"}

    def get_connection_info(self) -> Dict[str, Any]:
        """Get mock connection info"""
        return {
            "adapter_type": "mock_rest",
            "connected": self._is_connected,
            "request_count": len(self.request_history)
        }


class MockSOAPAdapter(BaseAdapter):
    """Mock SOAP adapter for testing"""

    def __init__(self, responses: Optional[str] = None, should_fail: bool = False):
        super().__init__()
        self.responses = responses or """
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <GetCaseResponse>
                        <Case>
                            <Id>soap-1</Id>
                            <Title>SOAP Case 1</Title>
                            <Status>Active</Status>
                        </Case>
                    </GetCaseResponse>
                </soap:Body>
            </soap:Envelope>
        """
        self.should_fail = should_fail
        self.request_history = []
        self._is_connected = False

    async def connect(self) -> bool:
        """Mock connection"""
        if self.should_fail:
            return False
        self._is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection"""
        self._is_connected = False

    async def call_operation(
        self,
        operation: str,
        parameters: Optional[Dict] = None
    ) -> str:
        """Mock SOAP operation call"""
        if self.should_fail:
            raise Exception("Mock SOAP call failure")

        self.request_history.append({
            "operation": operation,
            "parameters": parameters
        })
        return self.responses

    def get_connection_info(self) -> Dict[str, Any]:
        """Get mock connection info"""
        return {
            "adapter_type": "mock_soap",
            "connected": self._is_connected,
            "request_count": len(self.request_history)
        }
