# Testing Guide

## Overview

This directory contains comprehensive tests for the chatbot system, including unit tests, integration tests, and end-to-end tests.

## Test Structure

```
tests/
├── conftest.py                    # Pytest fixtures and configuration
├── mocks/                         # Mock data and utilities
│   ├── __init__.py
│   └── mock_responses.py          # Mock LLM and data adapter responses
├── test_integration_e2e.py        # End-to-end WebSocket tests
├── test_session_management.py     # Session management tests
├── test_data_adapters.py          # Data adapter tests
└── README.md                      # This file
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# End-to-end tests only
pytest -m e2e

# WebSocket tests
pytest -m websocket

# Database tests (requires PostgreSQL)
pytest -m postgres
```

### Run Specific Test File
```bash
pytest tests/test_integration_e2e.py
pytest tests/test_session_management.py
pytest tests/test_data_adapters.py
```

### Run Specific Test Function
```bash
pytest tests/test_integration_e2e.py::TestEndToEndFlow::test_chat_message_flow
```

### Run with Coverage
```bash
# Run tests with coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run with Verbose Output
```bash
pytest -v
pytest -vv  # Extra verbose
```

### Run Failed Tests Only
```bash
# Run only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

## Test Environment Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export CHATBOT_ENV=test
export REDIS_URL=redis://localhost:6379/1
export POSTGRES_URL=postgresql://test_user:test_password@localhost:5432/test_db
```

### 3. Start Required Services (Optional)
For integration tests with real services:

```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_DB=test_db \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_password \
  postgres:15-alpine
```

### 4. Using Docker Compose
```bash
# Start all services
docker-compose up -d

# Run tests in Docker
docker-compose exec backend pytest
```

## Test Configuration

### pytest.ini
Configuration file for pytest with:
- Test discovery patterns
- Coverage settings (minimum 80%)
- Async test support
- Custom markers

### conftest.py
Global fixtures including:
- Mock Redis client
- Mock PostgreSQL pool
- Mock Eliza provider
- Mock WebSocket handler
- Test configuration
- Sample test data

## Writing Tests

### Test Structure
```python
import pytest

class TestFeatureName:
    """Test suite for specific feature"""

    @pytest.mark.asyncio
    async def test_specific_behavior(self, fixture1, fixture2):
        """Test description"""
        # Arrange
        # ... setup test data

        # Act
        # ... execute code under test

        # Assert
        # ... verify results
```

### Using Fixtures
```python
@pytest.mark.asyncio
async def test_with_mock_session(self, mock_session_manager):
    session_id = await mock_session_manager.create_session()
    assert session_id is not None
```

### Testing WebSocket
```python
def test_websocket_flow(self, sync_test_client):
    with sync_test_client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"type": "chat", "content": "Hello"})
        response = ws.receive_json()
        assert response["type"] == "message"
```

### Testing Async Functions
```python
@pytest.mark.asyncio
async def test_async_function(self):
    result = await some_async_function()
    assert result is not None
```

## Test Categories

### Unit Tests
- Test individual components in isolation
- Fast execution
- No external dependencies
- Marker: `@pytest.mark.unit`

### Integration Tests
- Test interaction between components
- May use mock external services
- Moderate execution time
- Marker: `@pytest.mark.integration`

### End-to-End Tests
- Test complete user flows
- May require real services
- Slower execution
- Marker: `@pytest.mark.e2e`

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    pytest --cov=app --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Troubleshooting

### Tests Fail with Connection Errors
```bash
# Check if required services are running
docker ps

# Start services
docker-compose up -d redis postgres
```

### Async Tests Not Running
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Verify pytest.ini has asyncio_mode = auto
```

### Coverage Too Low
```bash
# Generate detailed coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Identify untested code and add tests
```

### WebSocket Tests Failing
```bash
# Ensure websocket-client is installed
pip install websocket-client

# Check FastAPI app is properly configured
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Use descriptive test names
3. **Coverage**: Aim for >80% code coverage
4. **Speed**: Keep tests fast with mocks
5. **Maintenance**: Update tests with code changes
6. **Documentation**: Document complex test scenarios
7. **Fixtures**: Reuse common setup via fixtures
8. **Markers**: Use markers to categorize tests
9. **Assertions**: Use clear, specific assertions
10. **Cleanup**: Clean up resources after tests

## Mock Data

### Available Mocks
- `MockLLMResponses`: LLM provider responses
- `MockDataAdapterResponses`: Database and API responses
- `MockSessionData`: Session and conversation history
- `MockWebSocketMessages`: WebSocket message formats

### Using Mocks
```python
from tests.mocks import MockLLMResponses

def test_with_mock_llm():
    mock_response = MockLLMResponses.get_case_status_response()
    # Use mock_response in test
```

## Performance Testing

### Load Testing WebSocket
```python
@pytest.mark.asyncio
async def test_concurrent_connections(self, sync_test_client):
    # Test with multiple concurrent connections
    connections = []
    for i in range(100):
        ws = sync_test_client.websocket_connect("/ws/chat")
        connections.append(ws)
```

### Benchmarking
```bash
# Install pytest-benchmark
pip install pytest-benchmark

# Run benchmark tests
pytest --benchmark-only
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
