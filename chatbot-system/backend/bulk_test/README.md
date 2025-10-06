# Bulk Testing Suite

Comprehensive testing suite for the Case Management Chatbot system with 50 sample questions covering various scenarios.

## Features

- ✅ 50 test questions covering all case management scenarios
- 📊 CSV output for easy analysis in Excel/Google Sheets
- 📈 Progress bar for real-time test execution tracking
- 🎯 Selective test execution (run specific tests)
- ⏱️ Performance metrics (fast/medium/slow response times)
- 🔄 Automatic retry on failures
- 📝 Detailed logs and summary reports
- ✨ **Smart Response Validation** - Detects error messages, API failures, and schema errors
- 🎯 **Quality Metrics** - True success rate based on response content, not just completion

## Installation

Install required dependencies:

```bash
pip install tqdm websockets aiohttp
```

## Usage

### Run All Tests

```bash
cd backend/bulk_test
python run_bulk_test.py
```

### Run Specific Tests

Run tests by ID (comma-separated):

```bash
python run_bulk_test.py --tests 1,2,3,14,18
```

### Custom Test Run ID

Specify a custom run ID for organizing results:

```bash
python run_bulk_test.py --run-id my_test_run
```

## Test Categories

The test suite includes questions from these categories:

1. **alert_summary** - List and summarize alerts with various filters
2. **alert_details** - Get specific alert details by ID
3. **alert_analysis** - Analyze alert patterns and trends
4. **cases** - Case management queries
5. **alert_types** - Alert type classification queries
6. **users** - User-related queries
7. **user_roles** - Role-based queries

## Complexity Levels

Each test is categorized by complexity:

- **simple** - Basic queries with single filters
- **medium** - Queries with multiple filters or specific IDs
- **high** - Complex analysis, comparisons, or aggregations

## Output Files

All results are saved in `bulk_test/test_results/`:

### 1. Results CSV (`results_<run_id>.csv`)

Columns:
- `test_id` - Test identifier
- `category` - Test category
- `complexity` - simple/medium/high
- `question` - User query
- `status` - success/content_error/api_rate_limit/incomplete_response/error/timeout
- `validation_status` - valid/error_detected/api_error/schema_error/incomplete
- `response_time_seconds` - Response time
- `tool_used` - Tool executed
- `filter_applied` - yes/no/unknown
- `response_length` - Response character count
- `response_text` - **Full response from the system**
- `validation_notes` - Details about validation issues found
- `error_message` - Error details (if any)
- `timestamp` - Test execution time
- `session_id` - WebSocket session ID

### 2. Summary Report (`summary_<run_id>.txt`)

Contains:
- Overall results (success, errors, timeouts, content errors, API rate limits, incomplete)
- **Quality Metrics** - Valid responses and true success rate
- Performance metrics (avg/min/max response times)
- Performance breakdown (fast/medium/slow)
- Category breakdown (success rate per category)
- Complexity breakdown (success rate per complexity)

### 3. Detailed Logs (`detailed_<run_id>.json`)

Full JSON logs including:
- All WebSocket messages
- Complete state transitions
- Timing information
- Full responses

## Configuration

Edit `config.py` to customize:

```python
TEST_CONFIG = {
    # Timeouts
    "query_timeout": 120,  # seconds

    # Performance thresholds
    "fast_response_threshold": 5.0,   # seconds
    "medium_response_threshold": 10.0, # seconds

    # Retry settings
    "retry_on_failure": True,
    "max_retries": 2,

    # Output
    "save_detailed_logs": True,
}
```

## Example Output

### Console Output

```
Running Tests: 100%|██████████| 50/50 [15:32<00:00, 18.6s/test]

================================================================================
BULK TEST SUMMARY
================================================================================
Total: 50 | Valid: 25 (50.0%) | Content Errors: 18 | API Limits: 7
Connection Errors: 0 | Timeouts: 0 | Incomplete: 0
Avg Time: 14.04s | Min: 6.27s | Max: 71.24s
Fast: 0 | Medium: 14 | Slow: 36
================================================================================
```

**Note:** The summary now shows the **True Success Rate** based on response quality validation, not just completion status. This helps identify actual failures vs. error messages.

### CSV Analysis

Open `results_*.csv` in Excel/Google Sheets to:
- Filter by category or complexity
- Sort by response time
- Identify failed tests
- Analyze performance patterns

## Test Examples

### Simple Query (ID: 1)
```
Question: "Show me all open alerts"
Expected: List of alerts with status='Open'
Tools: query_postgresql_cm_alerts
Filters: status = 'Open'
```

### Medium Query (ID: 14)
```
Question: "Summarize alert AML_20241120225734_LAY456789 for me"
Expected: Detailed alert summary by alert_id
Tools: query_postgresql_cm_alerts
Filters: alert_id = 'AML_20241120225734_LAY456789'
```

### High Complexity (ID: 18)
```
Question: "Compare alerts STID1025_ACC102445 and AML_20241120225734_LAY456789"
Expected: Comparative analysis of two alerts
Tools: query_postgresql_cm_alerts (multiple calls)
Filters: alert_id IN (...)
```

## Adding New Tests

Edit `test_questions.json`:

```json
{
  "id": 51,
  "category": "your_category",
  "complexity": "simple",
  "question": "Your test question",
  "expected_behavior": "What should happen",
  "expected_tools": ["tool_name"],
  "expected_filters": "field = 'value'",
  "tags": ["tag1", "tag2"]
}
```

Then rerun the test suite.

## Troubleshooting

### Backend Not Running

```
❌ Backend is not healthy. Aborting tests.
```

**Solution:** Start the backend server first:
```bash
cd backend
python -m uvicorn app.main:app --reload >> backend.log 2>&1 &
```

### Connection Timeout

```
⏱️ Timeout waiting for response
```

**Solution:** Increase timeout in `config.py`:
```python
"query_timeout": 180,  # 3 minutes
```

### Port Already in Use

```
Address already in use
```

**Solution:** Kill the process on port 8000:
```bash
lsof -i :8000
kill -9 <PID>
```

## Performance Benchmarks

Expected performance for a healthy system:

- **Simple queries**: < 5 seconds
- **Medium queries**: 5-10 seconds
- **High complexity**: 10-15 seconds

If queries consistently exceed 15 seconds, investigate:
1. Database query performance
2. LLM provider latency
3. Network connectivity

## Analysis Tips

### Using Excel/Google Sheets

1. Open `results_*.csv`
2. Create pivot table with:
   - Rows: category
   - Values: AVG(response_time_seconds), COUNT(status)
3. Create charts showing response time distribution

### Using Python

```python
import pandas as pd

df = pd.read_csv('test_results/results_*.csv')

# Average response time by category
print(df.groupby('category')['response_time_seconds'].mean())

# Success rate by complexity
print(df.groupby('complexity')['status'].value_counts())

# Slowest queries
print(df.nlargest(10, 'response_time_seconds')[['test_id', 'question', 'response_time_seconds']])
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Run Bulk Tests
  run: |
    cd backend/bulk_test
    python run_bulk_test.py --tests 1,5,10,14,18

- name: Check Success Rate
  run: |
    python -c "
    import pandas as pd
    df = pd.read_csv('test_results/results_*.csv')
    success_rate = (df['status'] == 'success').mean()
    assert success_rate >= 0.95, f'Success rate {success_rate} below 95%'
    "
```

## Support

For issues or questions:
1. Check `detailed_*.json` for full logs
2. Check backend logs in `backend.log`
3. Verify backend health: `curl http://localhost:8000/health`
