"""
Mock response generators for testing
"""
from typing import Dict, Any, List
import json
from datetime import datetime


class MockLLMResponses:
    """Mock responses for LLM provider testing"""

    @staticmethod
    def get_case_status_response() -> Dict[str, Any]:
        """Mock response for case status query"""
        return {
            "response": "Case #12345 is currently in 'Open' status. It was created on January 10, 2024, "
                       "and is assigned to Agent Sarah Johnson. The priority level is High, and the last "
                       "update was made 2 hours ago regarding customer account verification.",
            "message_id": "llm-msg-001",
            "usage": {
                "prompt_tokens": 45,
                "completion_tokens": 52,
                "total_tokens": 97
            },
            "metadata": {
                "model": "eliza-v1",
                "temperature": 0.7,
                "finish_reason": "stop"
            }
        }

    @staticmethod
    def get_list_cases_response() -> Dict[str, Any]:
        """Mock response for listing cases"""
        return {
            "response": "I found 5 open cases:\n\n"
                       "1. Case #12345 - Account Access Issue (High Priority)\n"
                       "2. Case #12346 - Payment Processing Error (Medium Priority)\n"
                       "3. Case #12347 - Data Sync Problem (Low Priority)\n"
                       "4. Case #12348 - Login Failure (High Priority)\n"
                       "5. Case #12349 - Report Generation Bug (Medium Priority)\n\n"
                       "Would you like details on any specific case?",
            "message_id": "llm-msg-002",
            "usage": {
                "prompt_tokens": 38,
                "completion_tokens": 89,
                "total_tokens": 127
            }
        }

    @staticmethod
    def get_streaming_chunks() -> List[str]:
        """Mock streaming response chunks"""
        return [
            "Based ",
            "on ",
            "the ",
            "database ",
            "query, ",
            "I ",
            "can ",
            "see ",
            "that ",
            "case ",
            "#12345 ",
            "has ",
            "the ",
            "following ",
            "details:\n\n",
            "- Status: Open\n",
            "- Priority: High\n",
            "- Assigned: Agent Sarah\n",
            "- Created: Jan 10, 2024\n\n",
            "The ",
            "customer ",
            "is ",
            "waiting ",
            "for ",
            "account ",
            "verification."
        ]

    @staticmethod
    def get_error_response() -> Dict[str, Any]:
        """Mock error response from LLM"""
        return {
            "error": "rate_limit_exceeded",
            "message": "API rate limit exceeded. Please try again later.",
            "retry_after": 60
        }


class MockDataAdapterResponses:
    """Mock responses for data adapter testing"""

    @staticmethod
    def get_postgres_cases() -> List[Dict[str, Any]]:
        """Mock PostgreSQL cases query result"""
        return [
            {
                "id": 12345,
                "title": "Account Access Issue",
                "status": "open",
                "priority": "high",
                "assigned_to": "agent-sarah-johnson",
                "created_at": "2024-01-10T09:30:00Z",
                "updated_at": "2024-01-15T14:22:00Z",
                "customer_id": "cust-001",
                "description": "Customer unable to access account after password reset"
            },
            {
                "id": 12346,
                "title": "Payment Processing Error",
                "status": "open",
                "priority": "medium",
                "assigned_to": "agent-mike-chen",
                "created_at": "2024-01-12T11:15:00Z",
                "updated_at": "2024-01-15T10:45:00Z",
                "customer_id": "cust-002",
                "description": "Transaction failing with error code E402"
            },
            {
                "id": 12347,
                "title": "Data Sync Problem",
                "status": "open",
                "priority": "low",
                "assigned_to": "agent-emma-davis",
                "created_at": "2024-01-13T08:00:00Z",
                "updated_at": "2024-01-14T16:30:00Z",
                "customer_id": "cust-003",
                "description": "Customer data not syncing across mobile and web"
            }
        ]

    @staticmethod
    def get_rest_api_case_details() -> Dict[str, Any]:
        """Mock REST API case details"""
        return {
            "case": {
                "id": "12345",
                "title": "Account Access Issue",
                "status": "open",
                "priority": "high",
                "customer": {
                    "id": "cust-001",
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "phone": "+1-555-0123"
                },
                "timeline": [
                    {
                        "timestamp": "2024-01-10T09:30:00Z",
                        "event": "case_created",
                        "actor": "system",
                        "details": "Case automatically created from support ticket"
                    },
                    {
                        "timestamp": "2024-01-10T10:15:00Z",
                        "event": "assigned",
                        "actor": "supervisor-001",
                        "details": "Assigned to Agent Sarah Johnson"
                    },
                    {
                        "timestamp": "2024-01-15T14:22:00Z",
                        "event": "status_update",
                        "actor": "agent-sarah-johnson",
                        "details": "Waiting for customer verification"
                    }
                ],
                "attachments": [
                    {
                        "id": "att-001",
                        "filename": "screenshot.png",
                        "type": "image/png",
                        "size": 245680,
                        "url": "/api/attachments/att-001"
                    }
                ]
            }
        }

    @staticmethod
    def get_oracle_transaction_data() -> List[Dict[str, Any]]:
        """Mock Oracle database transaction data"""
        return [
            {
                "transaction_id": "TXN-2024-001",
                "case_id": 12345,
                "amount": 1500.00,
                "currency": "USD",
                "status": "failed",
                "error_code": "E402",
                "timestamp": "2024-01-15T12:30:00Z",
                "payment_method": "credit_card",
                "card_last_four": "4532"
            },
            {
                "transaction_id": "TXN-2024-002",
                "case_id": 12345,
                "amount": 1500.00,
                "currency": "USD",
                "status": "pending_retry",
                "error_code": None,
                "timestamp": "2024-01-15T13:00:00Z",
                "payment_method": "credit_card",
                "card_last_four": "4532"
            }
        ]

    @staticmethod
    def get_soap_service_response() -> str:
        """Mock SOAP service XML response"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetCaseResponse xmlns="http://example.com/case-service">
            <Case>
                <CaseId>12345</CaseId>
                <Title>Account Access Issue</Title>
                <Status>Open</Status>
                <Priority>High</Priority>
                <CreatedDate>2024-01-10T09:30:00Z</CreatedDate>
                <AssignedAgent>
                    <AgentId>agent-sarah-johnson</AgentId>
                    <Name>Sarah Johnson</Name>
                    <Email>sarah.johnson@example.com</Email>
                </AssignedAgent>
            </Case>
        </GetCaseResponse>
    </soap:Body>
</soap:Envelope>"""


class MockSessionData:
    """Mock session data for testing"""

    @staticmethod
    def get_session_with_history() -> Dict[str, Any]:
        """Mock session with conversation history"""
        return {
            "session_id": "sess-test-001",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:15:00Z",
            "user_context": {
                "user_id": "user-123",
                "role": "customer_service",
                "permissions": ["view_cases", "update_cases"]
            },
            "conversation_history": [
                {
                    "role": "user",
                    "content": "Show me case #12345",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "message_id": "msg-001"
                },
                {
                    "role": "assistant",
                    "content": "Case #12345 is an Account Access Issue with high priority...",
                    "timestamp": "2024-01-15T10:00:05Z",
                    "message_id": "msg-002"
                },
                {
                    "role": "user",
                    "content": "What's the latest update?",
                    "timestamp": "2024-01-15T10:15:00Z",
                    "message_id": "msg-003"
                }
            ],
            "metadata": {
                "message_count": 3,
                "last_activity": "2024-01-15T10:15:00Z"
            }
        }

    @staticmethod
    def get_empty_session() -> Dict[str, Any]:
        """Mock new empty session"""
        return {
            "session_id": "sess-test-002",
            "created_at": "2024-01-15T11:00:00Z",
            "updated_at": "2024-01-15T11:00:00Z",
            "user_context": {},
            "conversation_history": [],
            "metadata": {
                "message_count": 0,
                "last_activity": "2024-01-15T11:00:00Z"
            }
        }


class MockWebSocketMessages:
    """Mock WebSocket message formats"""

    @staticmethod
    def get_connection_message(session_id: str) -> Dict[str, Any]:
        """Mock connection established message"""
        return {
            "type": "connection",
            "status": "connected",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def get_chat_message(content: str, message_id: str) -> Dict[str, Any]:
        """Mock chat message from user"""
        return {
            "type": "chat",
            "content": content,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def get_response_message(content: str, message_id: str) -> Dict[str, Any]:
        """Mock response message from assistant"""
        return {
            "type": "message",
            "content": content,
            "role": "assistant",
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def get_stream_chunk(content: str, done: bool = False) -> Dict[str, Any]:
        """Mock streaming chunk"""
        return {
            "type": "stream_chunk",
            "content": content,
            "done": done,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def get_action_message(action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock action message"""
        return {
            "type": "action",
            "action": action,
            "data": data,
            "message_id": f"action-{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    @staticmethod
    def get_error_message(error: str, details: str = None) -> Dict[str, Any]:
        """Mock error message"""
        return {
            "type": "error",
            "error": error,
            "message": details or "An error occurred",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
