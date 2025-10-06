# REST API Endpoint Configuration Guide

## Overview

This guide explains how to configure REST API endpoints so the chatbot can understand and interact with them intelligently.

## How It Works

### Architecture Flow

```
User Query → Intent Router → Endpoint Loader → REST API Tool → Your API → Response
              ↓
         Semantic Matcher
              ↓
         Query Planner
```

1. **User asks a question** (e.g., "Show me all high priority cases")
2. **Intent Router** analyzes the query using LangChain ReAct agent
3. **Endpoint Loader** finds matching API endpoints from configuration
4. **Semantic Matcher** selects the best endpoint based on description similarity
5. **Query Planner** constructs the API call with correct parameters
6. **REST API Tool** executes the call and returns formatted results

---

## Configuration Files

### 1. Main Endpoint Configuration: `api_endpoints.yaml`

**Location**: `/backend/app/config/api_endpoints.yaml`

This YAML file defines all available REST endpoints:

```yaml
endpoints:
  - name: "search_cases"
    description: "Search for cases based on criteria like status, priority, assigned to, date range"
    url: "${BASE_URL}/api/v1/cases/search"
    method: "POST"
    requires_auth: true
    parameters:
      - name: "status"
        type: "string"
        description: "Case status (open, closed, pending)"
        required: false
      - name: "priority"
        type: "string"
        description: "Case priority (low, medium, high, critical)"
        required: false
```

### 2. Environment Variables: `.env`

**Location**: `/chatbot-system/.env`

```bash
# API Configuration
API_BASE_URL=https://your-api.example.com
API_AUTH_TOKEN=your_bearer_token_here

# Or for development
API_BASE_URL=http://localhost:8080
API_AUTH_TOKEN=dev_token_12345
```

---

## Step-by-Step Configuration

### Step 1: Define Your Endpoints

Edit `/backend/app/config/api_endpoints.yaml`:

```yaml
endpoints:
  # Example 1: Simple GET endpoint
  - name: "get_user"
    description: "Get user information by user ID"
    url: "${BASE_URL}/api/users/{user_id}"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "user_id"
        type: "string"
        description: "User ID"
        required: true
        in: "path"  # Path parameter

  # Example 2: Search endpoint with query params
  - name: "search_cases"
    description: "Search cases by status, priority, date range, or assignee"
    url: "${BASE_URL}/api/cases/search"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "status"
        type: "string"
        description: "Filter by case status"
        required: false
        in: "query"  # Query parameter
      - name: "priority"
        type: "string"
        description: "Filter by priority level"
        required: false
        in: "query"

  # Example 3: POST endpoint with body
  - name: "create_case"
    description: "Create a new case with title and description"
    url: "${BASE_URL}/api/cases"
    method: "POST"
    requires_auth: true
    parameters:
      - name: "title"
        type: "string"
        description: "Case title"
        required: true
        in: "body"  # Body parameter
      - name: "description"
        type: "string"
        description: "Case description"
        required: true
        in: "body"
```

### Step 2: Configure Authentication

In `api_endpoints.yaml`, set the authentication type:

```yaml
# Bearer Token Authentication (most common)
authentication:
  type: "bearer"
  token_env_var: "API_AUTH_TOKEN"
  header_name: "Authorization"
  token_prefix: "Bearer"

# OR API Key Authentication
authentication:
  type: "api_key"
  token_env_var: "API_KEY"
  header_name: "X-API-Key"

# OR Basic Authentication
authentication:
  type: "basic"
  username_env_var: "API_USERNAME"
  password_env_var: "API_PASSWORD"
```

### Step 3: Set Environment Variables

Create or edit `.env` file:

```bash
# Required
API_BASE_URL=https://api.yourdomain.com
API_AUTH_TOKEN=your_actual_token_here

# Optional: Override defaults
API_TIMEOUT=60
API_RETRY_ATTEMPTS=3
```

### Step 4: Update Tool Registry

The chatbot will automatically load endpoints. To verify, check `/backend/app/main.py`:

```python
from app.config import get_endpoint_loader
from app.intelligence.tools.api_tool import RESTAPITool

# In your startup function
endpoint_loader = get_endpoint_loader()

# Create tools for each endpoint
for endpoint_def in endpoint_loader.get_all_endpoints():
    tool = RESTAPITool(
        name=f"api_{endpoint_def.name}",
        description=endpoint_def.description,
        base_url=endpoint_loader.config.default_base_url
    )
    tool_registry.register(tool)
```

---

## Real-World Examples

### Example 1: Case Management System

**Your existing API**:
```
GET  /api/v1/cases?status=open&priority=high
POST /api/v1/cases
GET  /api/v1/cases/{id}
PUT  /api/v1/cases/{id}
```

**Configuration** (`api_endpoints.yaml`):
```yaml
endpoints:
  - name: "list_cases"
    description: "Get list of cases with optional filters for status, priority, assignee"
    url: "${BASE_URL}/api/v1/cases"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "status"
        type: "string"
        description: "Filter by status: open, closed, pending"
        required: false
        in: "query"
      - name: "priority"
        type: "string"
        description: "Filter by priority: low, medium, high, critical"
        required: false
        in: "query"

  - name: "get_case_by_id"
    description: "Get detailed information for a specific case"
    url: "${BASE_URL}/api/v1/cases/{case_id}"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "case_id"
        type: "string"
        description: "Case ID"
        required: true
        in: "path"

  - name: "create_new_case"
    description: "Create a new case"
    url: "${BASE_URL}/api/v1/cases"
    method: "POST"
    requires_auth: true
    parameters:
      - name: "title"
        type: "string"
        description: "Case title"
        required: true
        in: "body"
      - name: "description"
        type: "string"
        description: "Case description"
        required: true
        in: "body"
      - name: "priority"
        type: "string"
        description: "Priority level"
        required: false
        default: "medium"
        in: "body"
```

**User conversations that will work**:
```
User: "Show me all high priority cases"
→ Calls: GET /api/v1/cases?priority=high

User: "What are the open cases assigned to John?"
→ Calls: GET /api/v1/cases?status=open&assignee=john

User: "Create a case titled 'Server Down' with high priority"
→ Calls: POST /api/v1/cases {"title": "Server Down", "priority": "high"}

User: "Get details for case #12345"
→ Calls: GET /api/v1/cases/12345
```

### Example 2: User Management

**Your API**:
```
GET /api/users
GET /api/users/{id}
POST /api/users
```

**Configuration**:
```yaml
endpoints:
  - name: "list_users"
    description: "Get all users or search users by name, email, department, or role"
    url: "${BASE_URL}/api/users"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "search"
        type: "string"
        description: "Search query for name or email"
        required: false
        in: "query"
      - name: "department"
        type: "string"
        description: "Filter by department"
        required: false
        in: "query"
      - name: "role"
        type: "string"
        description: "Filter by role"
        required: false
        in: "query"

  - name: "get_user_details"
    description: "Get detailed information about a specific user by ID or email"
    url: "${BASE_URL}/api/users/{user_id}"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "user_id"
        type: "string"
        description: "User ID or email address"
        required: true
        in: "path"
```

---

## How the Chatbot Identifies Endpoints

### 1. **Semantic Matching** (Primary Method)

The `SemanticMatcher` uses embedding similarity to find relevant endpoints:

```python
# User query: "Find all critical bugs"
#
# Semantic matcher compares query with endpoint descriptions:
#
# Endpoint: "Search cases by status and priority"
# Similarity score: 0.85 ✓ HIGH MATCH
#
# Endpoint: "Get user profile information"
# Similarity score: 0.12 ✗ LOW MATCH
```

**Tips for better matching**:
- Use **descriptive endpoint names** that include key terms
- Write **detailed descriptions** with synonyms and use cases
- Include **example queries** in descriptions

```yaml
# GOOD ✓
- name: "search_cases"
  description: "Search for cases, bugs, tickets, or issues by status (open/closed), priority (low/medium/high/critical), assignee, or date range"

# BAD ✗
- name: "search_cases"
  description: "Search cases"
```

### 2. **Intent Routing** (LangChain ReAct Agent)

The `IntentRouter` uses zero-shot reasoning:

```
User: "Show me John's high priority tasks from last week"

Agent Reasoning:
1. Intent: Search/Query
2. Entity: Tasks/Cases
3. Filters: assignee=John, priority=high, date_range=last_week
4. Best tool: search_cases endpoint
5. Parameters: {assignee: "John", priority: "high", date_from: "2024-09-24"}
```

### 3. **Query Planning** (Multi-Step Queries)

For complex queries requiring multiple API calls:

```
User: "Show me all critical cases and their assigned users"

Query Plan:
Step 1: Call search_cases with priority=critical
Step 2: For each case, extract assigned_user_id
Step 3: Call get_user_details for unique user IDs
Step 4: Merge case and user data
```

---

## Testing Your Configuration

### Step 1: Validate YAML Syntax

```bash
cd backend
python -c "from app.config import get_endpoint_loader; loader = get_endpoint_loader(); print(f'Loaded {len(loader.get_all_endpoints())} endpoints')"
```

### Step 2: Test Individual Endpoint

```python
from app.config import get_endpoint_loader

loader = get_endpoint_loader()

# Find endpoint
endpoint = loader.get_endpoint("search_cases")
print(f"Endpoint: {endpoint.name}")
print(f"URL: {endpoint.url}")
print(f"Method: {endpoint.method}")
print(f"Parameters: {[p.name for p in endpoint.parameters]}")
```

### Step 3: Test Semantic Matching

```python
from app.config import get_endpoint_loader

loader = get_endpoint_loader()

# Search by intent
matches = loader.get_endpoints_by_description("find high priority bugs")
for endpoint in matches:
    print(f"Match: {endpoint.name} - {endpoint.description}")
```

### Step 4: Test Full Integration

```bash
# Start the system
docker-compose up

# Connect to chatbot and test queries:
# "Show me all open cases"
# "Get case details for case #123"
# "Create a new case titled 'Test Case'"
```

---

## Advanced Configuration

### Custom Headers

```yaml
endpoints:
  - name: "special_api"
    url: "${BASE_URL}/api/special"
    method: "GET"
    requires_auth: true
    custom_headers:
      X-Custom-Header: "custom-value"
      X-Request-ID: "${REQUEST_ID}"  # Will be replaced at runtime
```

### Response Formatting

```yaml
endpoints:
  - name: "get_statistics"
    url: "${BASE_URL}/api/stats"
    method: "GET"
    response_format:
      type: "object"
      schema:
        total_cases: "integer"
        open_cases: "integer"
        closed_cases: "integer"
      format_template: |
        Statistics:
        - Total Cases: {total_cases}
        - Open: {open_cases}
        - Closed: {closed_cases}
```

### Rate Limiting

```yaml
# Global settings
timeout: 30
retry_attempts: 3
retry_delay: 1
rate_limit:
  requests_per_minute: 60
  burst: 10
```

### Multiple Environments

```yaml
# api_endpoints.yaml
base_url_env_var: "API_BASE_URL"
default_base_url: "http://localhost:8080"

# .env.development
API_BASE_URL=http://localhost:8080

# .env.staging
API_BASE_URL=https://staging-api.example.com

# .env.production
API_BASE_URL=https://api.example.com
```

---

## Troubleshooting

### Issue: Chatbot can't find my endpoint

**Solution**:
1. Check endpoint description is detailed and includes relevant keywords
2. Verify YAML syntax is valid
3. Restart the backend to reload configuration
4. Check logs for parsing errors

```bash
docker-compose logs backend | grep "endpoint"
```

### Issue: Wrong endpoint is being called

**Solution**:
1. Make endpoint descriptions more specific
2. Add negative keywords to other endpoints (e.g., "not for user management")
3. Increase semantic similarity threshold
4. Check IntentRouter logs to see reasoning

### Issue: Authentication failing

**Solution**:
1. Verify environment variable is set: `echo $API_AUTH_TOKEN`
2. Check token format matches API requirements
3. Test token manually: `curl -H "Authorization: Bearer $API_AUTH_TOKEN" <url>`
4. Verify `requires_auth: true` is set correctly

### Issue: Parameters not being passed correctly

**Solution**:
1. Check `in` field is correct: "path", "query", "body", or "header"
2. Verify parameter types match API expectations
3. Check `required` field is accurate
4. Review QueryPlanner logs for parameter extraction

---

## Summary

### Quick Start Checklist

- [ ] Copy `api_endpoints.yaml` to `/backend/app/config/`
- [ ] Define all your REST endpoints with clear descriptions
- [ ] Set authentication configuration
- [ ] Create `.env` file with `API_BASE_URL` and `API_AUTH_TOKEN`
- [ ] Test endpoint loading: `python -c "from app.config import get_endpoint_loader; ..."`
- [ ] Restart backend: `docker-compose restart backend`
- [ ] Test chatbot queries
- [ ] Monitor logs for errors
- [ ] Iterate on endpoint descriptions for better matching

### Key Files

```
chatbot-system/
├── backend/
│   ├── app/
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── api_endpoints.yaml        ← YOUR ENDPOINTS HERE
│   │   │   └── endpoint_loader.py        ← Loader logic
│   │   └── intelligence/
│   │       ├── intent_router.py          ← Intent detection
│   │       ├── semantic_matcher.py       ← Endpoint matching
│   │       ├── query_planner.py          ← Query planning
│   │       └── tools/
│   │           └── api_tool.py           ← REST API execution
│   └── .env                              ← API_BASE_URL, API_AUTH_TOKEN
└── ENDPOINT_CONFIGURATION_GUIDE.md       ← This file
```

---

## Need Help?

1. Check backend logs: `docker-compose logs -f backend`
2. Enable debug mode: Set `LOG_LEVEL=DEBUG` in `.env`
3. Review test cases: `backend/tests/integration/test_*.py`
4. Refer to existing examples in `api_endpoints.yaml`

The chatbot uses intelligent semantic matching and multi-step planning to automatically identify and call the right endpoints based on natural language queries. Focus on writing clear, descriptive endpoint configurations for best results!
