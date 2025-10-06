"""
Configuration for bulk testing suite.
"""
from pathlib import Path

# Test Configuration
TEST_CONFIG = {
    # Backend connection
    "websocket_url": "ws://localhost:8000/ws/chat",
    "health_check_url": "http://localhost:8000/health",

    # Paths
    "questions_file": "test_questions.json",
    "results_dir": "test_results",

    # Timeouts (seconds)
    "connection_timeout": 10,
    "query_timeout": 120,
    "health_check_timeout": 5,

    # Performance thresholds (seconds)
    "fast_response_threshold": 5.0,
    "medium_response_threshold": 10.0,
    "slow_response_threshold": 15.0,

    # Test execution
    "retry_on_failure": True,
    "max_retries": 2,
    "delay_between_tests": 1.0,  # seconds between tests

    # Output settings
    "csv_delimiter": ",",
    "timestamp_format": "%Y-%m-%d %H:%M:%S",
    "save_detailed_logs": True,

    # Validation
    "check_tool_usage": True,
    "check_filter_application": True,
    "check_response_quality": True,

    # Response quality validation
    "min_response_length": 50,  # Minimum chars for a valid response
    "validate_content": True,
}

# Response quality validation patterns
VALIDATION_PATTERNS = {
    # Error indicators in responses
    "error_keywords": [
        "I apologize for the error",
        "I apologize for",
        "cannot analyze",
        "cannot process",
        "unable to",
        "failed to",
        "could not",
        "something went wrong",
        "an error occurred",
        "Let me correct this",
        "Let me modify the query",
        "Let me try",
    ],

    # API-specific errors
    "api_errors": [
        "429 Too Many Requests",
        "Client error",
        "Connection error",
        "Connection timeout",
        "Service unavailable",
        "Internal server error",
        "Gateway timeout",
    ],

    # Database/schema errors
    "schema_errors": [
        "column name",
        "column does not exist",
        "table does not exist",
        "invalid column",
        "syntax error",
        "relation does not exist",
    ],

    # Incomplete/unhelpful responses
    "incomplete_indicators": [
        "I apologize, but I cannot",
        "without more context",
        "without additional information",
        "I would need",
        "please provide",
    ],
}

# Test categories and their weights for analysis
CATEGORY_WEIGHTS = {
    "alert_summary": 1.5,      # High priority
    "alert_details": 1.5,      # High priority
    "alert_analysis": 2.0,     # Highest priority
    "cases": 1.2,
    "alert_types": 1.0,
    "users": 1.0,
    "user_roles": 0.8,
}

# Complexity scores
COMPLEXITY_SCORES = {
    "simple": 1,
    "medium": 2,
    "high": 3,
}

# CSV output columns
CSV_COLUMNS = [
    "test_id",
    "category",
    "complexity",
    "question",
    "status",
    "validation_status",
    "response_time_seconds",
    "tool_used",
    "filter_applied",
    "response_length",
    "response_text",
    "validation_notes",
    "error_message",
    "timestamp",
    "session_id",
]

def get_results_path(test_run_id: str) -> Path:
    """Get path for test results CSV file."""
    results_dir = Path(__file__).parent / TEST_CONFIG["results_dir"]
    results_dir.mkdir(exist_ok=True)
    return results_dir / f"results_{test_run_id}.csv"

def get_summary_path(test_run_id: str) -> Path:
    """Get path for test summary file."""
    results_dir = Path(__file__).parent / TEST_CONFIG["results_dir"]
    results_dir.mkdir(exist_ok=True)
    return results_dir / f"summary_{test_run_id}.txt"

def get_detailed_log_path(test_run_id: str) -> Path:
    """Get path for detailed test logs."""
    results_dir = Path(__file__).parent / TEST_CONFIG["results_dir"]
    results_dir.mkdir(exist_ok=True)
    return results_dir / f"detailed_{test_run_id}.json"
