#!/usr/bin/env python3
"""
Bulk Testing Suite for Case Management Chatbot.

This script runs comprehensive tests against the chatbot system,
executing multiple questions and collecting detailed metrics.
"""
import asyncio
import json
import csv
import time
import logging
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import websockets
import aiohttp
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bulk_test.config import (
    TEST_CONFIG,
    CATEGORY_WEIGHTS,
    COMPLEXITY_SCORES,
    CSV_COLUMNS,
    VALIDATION_PATTERNS,
    get_results_path,
    get_summary_path,
    get_detailed_log_path,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BulkTester:
    """Main class for running bulk tests."""

    def __init__(self, test_run_id: str):
        """Initialize bulk tester."""
        self.test_run_id = test_run_id
        self.results: List[Dict[str, Any]] = []
        self.detailed_logs: List[Dict[str, Any]] = []
        self.questions: List[Dict[str, Any]] = []

        # Load questions
        questions_path = Path(__file__).parent / TEST_CONFIG["questions_file"]
        with open(questions_path, 'r') as f:
            data = json.load(f)
            self.questions = data["questions"]

        logger.info(f"📋 Loaded {len(self.questions)} test questions")

    def validate_response_quality(self, response_text: str) -> tuple[str, str]:
        """
        Validate response quality and detect errors.

        Returns:
            tuple: (validation_status, validation_notes)
                validation_status: "valid", "error_detected", "api_error", "schema_error", "incomplete"
                validation_notes: Description of any issues found
        """
        if not response_text or len(response_text.strip()) == 0:
            return ("empty_response", "Response is empty")

        response_lower = response_text.lower()

        # Check for API errors (highest priority)
        for pattern in VALIDATION_PATTERNS["api_errors"]:
            if pattern.lower() in response_lower:
                return ("api_error", f"API error detected: {pattern}")

        # Check for database/schema errors
        for pattern in VALIDATION_PATTERNS["schema_errors"]:
            if pattern.lower() in response_lower:
                return ("schema_error", f"Database schema error: {pattern}")

        # Check for general error keywords
        for pattern in VALIDATION_PATTERNS["error_keywords"]:
            if pattern.lower() in response_lower:
                return ("error_detected", f"Error message detected: '{pattern}'")

        # Check for incomplete/unhelpful responses
        for pattern in VALIDATION_PATTERNS["incomplete_indicators"]:
            if pattern.lower() in response_lower:
                return ("incomplete", f"Incomplete response: {pattern}")

        # Check minimum length
        if len(response_text) < TEST_CONFIG.get("min_response_length", 50):
            return ("too_short", f"Response too short ({len(response_text)} chars)")

        # All checks passed
        return ("valid", "Response appears valid")

    async def check_backend_health(self) -> bool:
        """Check if backend is healthy before running tests."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    TEST_CONFIG["health_check_url"],
                    timeout=aiohttp.ClientTimeout(total=TEST_CONFIG["health_check_timeout"])
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Backend health check passed: {data.get('status')}")
                        return True
                    else:
                        logger.error(f"❌ Backend health check failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"❌ Backend health check error: {e}")
            return False

    async def execute_single_test(
        self,
        question_data: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Execute a single test question."""
        test_id = question_data["id"]
        question = question_data["question"]

        logger.info(f"\n{'='*80}")
        logger.info(f"🧪 Test #{test_id}: {question}")
        logger.info(f"   Category: {question_data['category']} | Complexity: {question_data['complexity']}")
        logger.info(f"{'='*80}")

        result = {
            "test_id": test_id,
            "category": question_data["category"],
            "complexity": question_data["complexity"],
            "question": question,
            "status": "pending",
            "validation_status": "pending",
            "response_time_seconds": 0.0,
            "tool_used": "",
            "filter_applied": "",
            "response_length": 0,
            "response_text": "",
            "validation_notes": "",
            "error_message": "",
            "timestamp": datetime.now().strftime(TEST_CONFIG["timestamp_format"]),
            "session_id": "",
        }

        detailed_log = {
            "test_id": test_id,
            "question_data": question_data,
            "messages": [],
            "start_time": time.time(),
        }

        try:
            start_time = time.time()

            # Connect to WebSocket
            async with websockets.connect(
                TEST_CONFIG["websocket_url"],
                open_timeout=TEST_CONFIG["connection_timeout"]
            ) as websocket:
                # Get session ID from initial message
                initial_msg = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=TEST_CONFIG["connection_timeout"]
                )
                initial_data = json.loads(initial_msg)
                session_id = initial_data.get("session_id", "unknown")
                result["session_id"] = session_id
                detailed_log["session_id"] = session_id

                logger.info(f"🔌 Connected to session: {session_id}")

                # Send query
                query_message = {
                    "type": "chat",
                    "content": question,
                    "id": f"test_{test_id}"
                }
                await websocket.send(json.dumps(query_message))
                logger.info(f"📤 Sent query")

                # Collect response
                full_response = ""
                tool_used = ""
                filter_applied = ""

                while True:
                    try:
                        response = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=TEST_CONFIG["query_timeout"]
                        )
                        data = json.loads(response)
                        detailed_log["messages"].append(data)

                        msg_type = data.get("type")

                        if msg_type == "stream_chunk":
                            # Streaming response chunk
                            chunk = data.get("content", "")
                            full_response += chunk

                        elif msg_type == "stream_complete":
                            # Stream completed successfully
                            logger.info(f"✅ Stream completed")
                            break

                        elif msg_type == "response":
                            # Complete response (non-streaming mode)
                            full_response = data.get("content", "")
                            metadata = data.get("metadata", {})

                            # Extract tool information
                            if "tool_used" in metadata:
                                tool_used = metadata["tool_used"]

                            # Extract filter information
                            if "sql_query" in metadata:
                                sql = metadata["sql_query"]
                                if "WHERE" in sql.upper():
                                    filter_applied = "yes"
                                else:
                                    filter_applied = "no"
                            break

                        elif msg_type == "node_update":
                            # LangGraph node execution update
                            node_name = data.get("node", "unknown")
                            logger.debug(f"📍 Node: {node_name}")

                        elif msg_type == "message_received":
                            # Acknowledgment - continue
                            logger.debug(f"✅ Message received by backend")

                        elif msg_type == "error":
                            # Error occurred
                            error_msg = data.get("message", data.get("content", "Unknown error"))
                            logger.error(f"❌ Error from backend: {error_msg}")
                            result["status"] = "error"
                            result["error_message"] = error_msg
                            break

                    except asyncio.TimeoutError:
                        logger.warning(f"⏱️ Timeout waiting for response")
                        result["status"] = "timeout"
                        result["error_message"] = "Query timeout"
                        break

                end_time = time.time()
                response_time = end_time - start_time

                # Update result
                if result["status"] != "error" and result["status"] != "timeout":
                    result["status"] = "success"
                    result["response_time_seconds"] = round(response_time, 2)
                    result["tool_used"] = tool_used
                    result["filter_applied"] = filter_applied
                    result["response_length"] = len(full_response)
                    result["response_text"] = full_response

                    # Validate response quality
                    validation_status, validation_notes = self.validate_response_quality(full_response)
                    result["validation_status"] = validation_status
                    result["validation_notes"] = validation_notes

                    # Update status based on validation
                    if validation_status == "api_error":
                        result["status"] = "api_rate_limit"
                    elif validation_status in ["error_detected", "schema_error"]:
                        result["status"] = "content_error"
                    elif validation_status in ["incomplete", "too_short", "empty_response"]:
                        result["status"] = "incomplete_response"

                    # Performance categorization
                    if response_time <= TEST_CONFIG["fast_response_threshold"]:
                        perf = "FAST ⚡"
                    elif response_time <= TEST_CONFIG["medium_response_threshold"]:
                        perf = "MEDIUM 🔄"
                    else:
                        perf = "SLOW 🐌"

                    logger.info(f"✅ Test #{test_id} completed in {response_time:.2f}s [{perf}]")
                    logger.info(f"   Tool: {tool_used or 'none'}")
                    logger.info(f"   Filter: {filter_applied or 'unknown'}")
                    logger.info(f"   Response length: {len(full_response)} chars")
                    logger.info(f"   Validation: {validation_status} - {validation_notes}")

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"❌ WebSocket error: {e}")
            result["status"] = "connection_error"
            result["error_message"] = str(e)

            # Retry logic
            if TEST_CONFIG["retry_on_failure"] and retry_count < TEST_CONFIG["max_retries"]:
                logger.info(f"🔄 Retrying test #{test_id} (attempt {retry_count + 2}/{TEST_CONFIG['max_retries'] + 1})...")
                await asyncio.sleep(2)
                return await self.execute_single_test(question_data, retry_count + 1)

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            result["status"] = "error"
            result["error_message"] = str(e)

        detailed_log["end_time"] = time.time()
        detailed_log["result"] = result

        self.results.append(result)
        self.detailed_logs.append(detailed_log)

        return result

    async def run_tests(self, test_ids: Optional[List[int]] = None) -> None:
        """Run all tests or specific test IDs."""
        # Filter questions if test_ids provided
        if test_ids:
            questions_to_run = [q for q in self.questions if q["id"] in test_ids]
            logger.info(f"🎯 Running {len(questions_to_run)} selected tests")
        else:
            questions_to_run = self.questions
            logger.info(f"🎯 Running all {len(questions_to_run)} tests")

        # Check backend health
        if not await self.check_backend_health():
            logger.error("❌ Backend is not healthy. Aborting tests.")
            return

        # Run tests with progress bar
        with tqdm(total=len(questions_to_run), desc="Running Tests", unit="test") as pbar:
            for i, question_data in enumerate(questions_to_run, 1):
                # Update progress bar description with current test
                test_desc = f"Test #{question_data['id']} ({question_data['category']})"
                pbar.set_description(test_desc)

                logger.info(f"\n{'#'*80}")
                logger.info(f"Progress: {i}/{len(questions_to_run)}")
                logger.info(f"{'#'*80}")

                result = await self.execute_single_test(question_data)

                # Update progress bar with result
                status_emoji = "✅" if result["status"] == "success" else "❌"
                pbar.set_postfix_str(f"{status_emoji} {result['status']}")
                pbar.update(1)

                # Delay between tests
                if i < len(questions_to_run):
                    await asyncio.sleep(TEST_CONFIG["delay_between_tests"])

        logger.info(f"\n{'='*80}")
        logger.info("🏁 All tests completed!")
        logger.info(f"{'='*80}")

    def save_results(self) -> None:
        """Save test results to CSV and summary files."""
        # Save CSV
        csv_path = get_results_path(self.test_run_id)
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=TEST_CONFIG["csv_delimiter"])
            writer.writeheader()
            writer.writerows(self.results)
        logger.info(f"💾 Results saved to: {csv_path}")

        # Save detailed logs
        if TEST_CONFIG["save_detailed_logs"]:
            log_path = get_detailed_log_path(self.test_run_id)
            with open(log_path, 'w') as f:
                json.dump(self.detailed_logs, f, indent=2)
            logger.info(f"💾 Detailed logs saved to: {log_path}")

        # Generate summary
        self.generate_summary()

    def generate_summary(self) -> None:
        """Generate test summary report."""
        summary_path = get_summary_path(self.test_run_id)

        total = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "success")
        error = sum(1 for r in self.results if r["status"] == "error")
        timeout = sum(1 for r in self.results if r["status"] == "timeout")

        # Quality-based status counts
        content_error = sum(1 for r in self.results if r["status"] == "content_error")
        api_rate_limit = sum(1 for r in self.results if r["status"] == "api_rate_limit")
        incomplete = sum(1 for r in self.results if r["status"] == "incomplete_response")

        # Validation status breakdown
        valid_responses = sum(1 for r in self.results if r.get("validation_status") == "valid")
        quality_rate = (valid_responses / total * 100) if total > 0 else 0

        success_rate = (success / total * 100) if total > 0 else 0

        # Calculate response time stats
        success_times = [r["response_time_seconds"] for r in self.results if r["status"] == "success"]
        avg_time = sum(success_times) / len(success_times) if success_times else 0
        min_time = min(success_times) if success_times else 0
        max_time = max(success_times) if success_times else 0

        # Performance breakdown
        fast = sum(1 for t in success_times if t <= TEST_CONFIG["fast_response_threshold"])
        medium = sum(1 for t in success_times if TEST_CONFIG["fast_response_threshold"] < t <= TEST_CONFIG["medium_response_threshold"])
        slow = sum(1 for t in success_times if t > TEST_CONFIG["medium_response_threshold"])

        # Category breakdown
        category_stats = {}
        for result in self.results:
            cat = result["category"]
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "success": 0}
            category_stats[cat]["total"] += 1
            if result["status"] == "success":
                category_stats[cat]["success"] += 1

        # Complexity breakdown
        complexity_stats = {}
        for result in self.results:
            comp = result["complexity"]
            if comp not in complexity_stats:
                complexity_stats[comp] = {"total": 0, "success": 0}
            complexity_stats[comp]["total"] += 1
            if result["status"] == "success":
                complexity_stats[comp]["success"] += 1

        # Write summary
        with open(summary_path, 'w') as f:
            f.write("="*80 + "\n")
            f.write("BULK TEST SUMMARY\n")
            f.write("="*80 + "\n\n")

            f.write(f"Test Run ID: {self.test_run_id}\n")
            f.write(f"Timestamp: {datetime.now().strftime(TEST_CONFIG['timestamp_format'])}\n\n")

            f.write("OVERALL RESULTS\n")
            f.write("-"*80 + "\n")
            f.write(f"Total Tests: {total}\n")
            f.write(f"Success (no errors): {success} ({success_rate:.1f}%)\n")
            f.write(f"Connection Errors: {error}\n")
            f.write(f"Timeouts: {timeout}\n")
            f.write(f"Content Errors: {content_error}\n")
            f.write(f"API Rate Limits: {api_rate_limit}\n")
            f.write(f"Incomplete Responses: {incomplete}\n\n")

            f.write("QUALITY METRICS\n")
            f.write("-"*80 + "\n")
            f.write(f"Valid Responses: {valid_responses}/{total} ({quality_rate:.1f}%)\n")
            f.write(f"True Success Rate: {quality_rate:.1f}%\n\n")

            f.write("PERFORMANCE METRICS\n")
            f.write("-"*80 + "\n")
            f.write(f"Average Response Time: {avg_time:.2f}s\n")
            f.write(f"Min Response Time: {min_time:.2f}s\n")
            f.write(f"Max Response Time: {max_time:.2f}s\n\n")
            f.write(f"Fast (<{TEST_CONFIG['fast_response_threshold']}s): {fast}\n")
            f.write(f"Medium ({TEST_CONFIG['fast_response_threshold']}-{TEST_CONFIG['medium_response_threshold']}s): {medium}\n")
            f.write(f"Slow (>{TEST_CONFIG['medium_response_threshold']}s): {slow}\n\n")

            f.write("CATEGORY BREAKDOWN\n")
            f.write("-"*80 + "\n")
            for cat, stats in sorted(category_stats.items()):
                rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
                f.write(f"{cat:20s}: {stats['success']}/{stats['total']} ({rate:.1f}%)\n")
            f.write("\n")

            f.write("COMPLEXITY BREAKDOWN\n")
            f.write("-"*80 + "\n")
            for comp, stats in sorted(complexity_stats.items()):
                rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
                f.write(f"{comp:10s}: {stats['success']}/{stats['total']} ({rate:.1f}%)\n")
            f.write("\n")

            f.write("="*80 + "\n")

        logger.info(f"📊 Summary saved to: {summary_path}")

        # Print summary to console
        print("\n" + "="*80)
        print("BULK TEST SUMMARY")
        print("="*80)
        print(f"Total: {total} | Valid: {valid_responses} ({quality_rate:.1f}%) | Content Errors: {content_error} | API Limits: {api_rate_limit}")
        print(f"Connection Errors: {error} | Timeouts: {timeout} | Incomplete: {incomplete}")
        print(f"Avg Time: {avg_time:.2f}s | Min: {min_time:.2f}s | Max: {max_time:.2f}s")
        print(f"Fast: {fast} | Medium: {medium} | Slow: {slow}")
        print("="*80 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run bulk tests for Case Management Chatbot")
    parser.add_argument(
        "--tests",
        type=str,
        help="Comma-separated test IDs to run (e.g., 1,2,3). If not provided, runs all tests."
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=datetime.now().strftime("%Y%m%d_%H%M%S"),
        help="Test run ID (default: timestamp)"
    )

    args = parser.parse_args()

    # Parse test IDs
    test_ids = None
    if args.tests:
        test_ids = [int(x.strip()) for x in args.tests.split(",")]
        logger.info(f"🎯 Running tests: {test_ids}")

    # Create tester
    tester = BulkTester(test_run_id=args.run_id)

    # Run tests
    await tester.run_tests(test_ids=test_ids)

    # Save results
    tester.save_results()

    logger.info("✅ Bulk testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
