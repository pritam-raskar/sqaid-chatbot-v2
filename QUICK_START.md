# Quick Start Guide - REST Endpoint Configuration

## Overview

This chatbot uses **intelligent semantic matching** to automatically identify which REST API endpoints to call based on natural language queries. You don't need to write code - just configure your endpoints in YAML.

## How It Works (30 Second Summary)

```
1. You define your API endpoints in YAML
2. Chatbot reads endpoint descriptions
3. User asks a question in natural language
4. Chatbot matches question → best endpoint
5. Chatbot calls your API → returns results
```

**Example:**
```yaml
- name: "search_cases"
  description: "Search for cases by status, priority, or assignee"
  url: "${BASE_URL}/api/cases/search"
  method: "POST"
```

**User asks:** "Show me all high priority cases"
**Chatbot:** Automatically calls `POST /api/cases/search` with `{priority: "high"}`

---

## 5-Minute Setup

### Step 1: Configure Your API Endpoints

Edit: `chatbot-system/backend/app/config/api_endpoints.yaml`

```yaml
endpoints:
  - name: "your_endpoint_name"
    description: "Clear description with keywords user might say"
    url: "${BASE_URL}/your/endpoint/path"
    method: "GET"  # or POST, PUT, DELETE
    requires_auth: true
    parameters:
      - name: "param_name"
        type: "string"
        description: "What this parameter does"
        required: false
        in: "query"  # or path, body, header
```

### Step 2: Set Environment Variables

Create `.env` file:

```bash
cp chatbot-system/.env.example chatbot-system/.env
```

Edit `.env`:
```bash
API_BASE_URL=https://your-api.example.com
API_AUTH_TOKEN=your_bearer_token_here
```

### Step 3: Test Configuration

```bash
cd chatbot-system/backend
python -c "
from app.config import get_endpoint_loader
loader = get_endpoint_loader()
print(f'✓ Loaded {len(loader.get_all_endpoints())} endpoints')
for ep in loader.get_all_endpoints():
    print(f'  - {ep.name}: {ep.url}')
"
```

### Step 4: Start Chatbot

```bash
cd chatbot-system
docker-compose up --build
```

### Step 5: Test Queries

Open browser to `http://localhost:3000` and try:
- "Show me all open cases"
- "Get details for case #123"
- "Create a new case titled 'Test'"

---

## Real-World Example: Case Management System

### Your Existing API

```
GET  /api/v1/cases?status=open&priority=high
POST /api/v1/cases
GET  /api/v1/cases/12345
PUT  /api/v1/cases/12345
GET  /api/v1/users/john@example.com
```

### Configuration (5 minutes)

**1. Edit `api_endpoints.yaml`:**

```yaml
endpoints:
  # Search cases
  - name: "search_cases"
    description: "Search for cases by status, priority, assignee, or date range"
    url: "${BASE_URL}/api/v1/cases"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "status"
        type: "string"
        description: "Filter by status (open, closed, pending)"
        required: false
        in: "query"
      - name: "priority"
        type: "string"
        description: "Filter by priority (low, medium, high, critical)"
        required: false
        in: "query"

  # Get case details
  - name: "get_case_details"
    description: "Get detailed information for a specific case by ID"
    url: "${BASE_URL}/api/v1/cases/{case_id}"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "case_id"
        type: "string"
        description: "Case ID or number"
        required: true
        in: "path"

  # Create case
  - name: "create_case"
    description: "Create a new case with title and description"
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

  # Get user info
  - name: "get_user"
    description: "Get user information by email or ID"
    url: "${BASE_URL}/api/v1/users/{user_id}"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "user_id"
        type: "string"
        description: "User email or ID"
        required: true
        in: "path"
```

**2. Edit `.env`:**

```bash
API_BASE_URL=https://api.yourcompany.com
API_AUTH_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**3. That's it!** Restart the backend:

```bash
docker-compose restart backend
```

### What Works Now

**User conversations that automatically work:**

| User Says | Chatbot Does |
|-----------|--------------|
| "Show me all high priority cases" | `GET /api/v1/cases?priority=high` |
| "Find open cases assigned to John" | `GET /api/v1/cases?status=open&assignee=john` |
| "Get details for case 12345" | `GET /api/v1/cases/12345` |
| "Create a case: Server is down" | `POST /api/v1/cases {"title": "Server is down", ...}` |
| "Who is john@example.com?" | `GET /api/v1/users/john@example.com` |
| "Show critical bugs from last week" | `GET /api/v1/cases?priority=critical&date_from=...` |

---

## Configuration Tips

### 1. Write Good Descriptions

✅ **GOOD:**
```yaml
description: "Search for cases, tickets, bugs, or issues by status, priority, assignee, date range, or keywords"
```

❌ **BAD:**
```yaml
description: "Search cases"
```

**Why?** The chatbot uses semantic similarity to match user queries. More keywords = better matching.

### 2. Use Descriptive Parameter Names

✅ **GOOD:**
```yaml
parameters:
  - name: "status"
    description: "Case status: open, closed, pending, in_progress, resolved"
```

❌ **BAD:**
```yaml
parameters:
  - name: "s"
    description: "Status"
```

### 3. Specify Parameter Location Correctly

```yaml
in: "path"   # For URL path: /cases/{id}
in: "query"  # For query params: /cases?status=open
in: "body"   # For request body (POST/PUT)
in: "header" # For custom headers
```

### 4. Use ${BASE_URL} Placeholder

```yaml
url: "${BASE_URL}/api/v1/cases"  # ✅ GOOD
url: "http://localhost:8000/api/v1/cases"  # ❌ BAD (hardcoded)
```

---

## Common Scenarios

### Scenario 1: Path Parameters

**Your API:** `GET /api/users/12345/profile`

**Configuration:**
```yaml
- name: "get_user_profile"
  description: "Get user profile information"
  url: "${BASE_URL}/api/users/{user_id}/profile"
  method: "GET"
  parameters:
    - name: "user_id"
      type: "string"
      description: "User ID"
      required: true
      in: "path"  # ← Important!
```

### Scenario 2: Query Parameters

**Your API:** `GET /api/cases?status=open&priority=high&limit=10`

**Configuration:**
```yaml
- name: "search_cases"
  description: "Search cases"
  url: "${BASE_URL}/api/cases"
  method: "GET"
  parameters:
    - name: "status"
      in: "query"  # ← All query params
    - name: "priority"
      in: "query"
    - name: "limit"
      in: "query"
      default: 50
```

### Scenario 3: POST with Body

**Your API:** `POST /api/cases` with JSON body

**Configuration:**
```yaml
- name: "create_case"
  description: "Create a new case"
  url: "${BASE_URL}/api/cases"
  method: "POST"
  parameters:
    - name: "title"
      in: "body"  # ← All body params
    - name: "description"
      in: "body"
    - name: "priority"
      in: "body"
      default: "medium"
```

### Scenario 4: Custom Headers

**Your API:** Requires `X-Custom-Header: value`

**Configuration:**
```yaml
- name: "special_endpoint"
  description: "Special API call"
  url: "${BASE_URL}/api/special"
  method: "GET"
  parameters:
    - name: "X-Custom-Header"
      type: "string"
      description: "Custom header value"
      required: true
      in: "header"  # ← Custom header
```

### Scenario 5: Different Authentication

**Bearer Token (most common):**
```yaml
authentication:
  type: "bearer"
  token_env_var: "API_AUTH_TOKEN"
  header_name: "Authorization"
  token_prefix: "Bearer"
```

**API Key:**
```yaml
authentication:
  type: "api_key"
  token_env_var: "API_KEY"
  header_name: "X-API-Key"
```

**Basic Auth:**
```yaml
authentication:
  type: "basic"
  username_env_var: "API_USERNAME"
  password_env_var: "API_PASSWORD"
```

---

## Testing Your Configuration

### Test 1: Validate YAML Syntax

```bash
cd chatbot-system/backend
python -c "
import yaml
with open('app/config/api_endpoints.yaml') as f:
    config = yaml.safe_load(f)
print('✓ YAML is valid')
print(f'✓ Found {len(config[\"endpoints\"])} endpoints')
"
```

### Test 2: Load Endpoints

```bash
python -c "
from app.config import get_endpoint_loader
loader = get_endpoint_loader()
print(f'✓ Loaded {len(loader.get_all_endpoints())} endpoints')
for ep in loader.get_all_endpoints():
    print(f'  - {ep.name}: {ep.method} {ep.url}')
"
```

### Test 3: Test Semantic Matching

```bash
python -c "
from app.config import get_endpoint_loader
loader = get_endpoint_loader()
matches = loader.get_endpoints_by_description('find high priority bugs')
print('Matching endpoints:')
for ep in matches:
    print(f'  - {ep.name}: {ep.description}')
"
```

### Test 4: Check Authentication

```bash
python -c "
from app.config import get_endpoint_loader
loader = get_endpoint_loader()
headers = loader.build_headers()
print('Auth headers:', headers)
"
```

### Test 5: Test End-to-End

```bash
# Start the system
docker-compose up -d

# Check logs
docker-compose logs -f backend

# Test via chatbot UI
# Open: http://localhost:3000
# Try: "Show me all open cases"
```

---

## Troubleshooting

### Issue: "Endpoint not found"

**Possible causes:**
1. Endpoint description doesn't match user query
2. YAML syntax error
3. Config file not reloaded

**Solutions:**
```bash
# 1. Make description more detailed
description: "Search for cases, tickets, bugs, or issues by status, priority, assignee"

# 2. Validate YAML
python -c "import yaml; yaml.safe_load(open('app/config/api_endpoints.yaml'))"

# 3. Restart backend
docker-compose restart backend
```

### Issue: "Authentication failed"

**Solutions:**
```bash
# Check token is set
echo $API_AUTH_TOKEN

# Test manually
curl -H "Authorization: Bearer $API_AUTH_TOKEN" $API_BASE_URL/api/v1/cases

# Check .env file is loaded
docker-compose config | grep API_AUTH_TOKEN
```

### Issue: "Wrong parameters sent"

**Solutions:**
1. Check `in` field is correct (path, query, body, header)
2. Verify parameter types match API
3. Check `required` field
4. Review chatbot logs

```bash
# Enable debug logging
LOG_LEVEL=DEBUG docker-compose up backend
```

### Issue: "Timeout errors"

**Solutions:**
```bash
# Increase timeout in api_endpoints.yaml
timeout: 60  # seconds

# Or in .env
API_TIMEOUT=60
```

---

## Next Steps

### 1. Add More Endpoints

Copy an existing endpoint definition and modify:

```yaml
- name: "your_new_endpoint"
  description: "What it does with keywords"
  url: "${BASE_URL}/your/path"
  method: "GET"
  requires_auth: true
  parameters:
    - name: "param1"
      type: "string"
      description: "What this does"
      required: false
      in: "query"
```

### 2. Test with Real Users

Monitor logs to see which endpoints are being called:

```bash
docker-compose logs -f backend | grep "Calling endpoint"
```

### 3. Improve Matching

If wrong endpoints are being called:
1. Make descriptions more specific
2. Add negative keywords (e.g., "not for user management")
3. Review semantic matcher logs

### 4. Add Custom Logic (Optional)

For complex scenarios, you can extend:
- `backend/app/intelligence/intent_router.py` - Intent detection
- `backend/app/intelligence/query_planner.py` - Multi-step queries
- `backend/app/intelligence/semantic_matcher.py` - Endpoint matching

---

## Summary

### Checklist

- [ ] Copy `.env.example` to `.env`
- [ ] Set `API_BASE_URL` in `.env`
- [ ] Set `API_AUTH_TOKEN` in `.env`
- [ ] Edit `api_endpoints.yaml` with your endpoints
- [ ] Test YAML syntax
- [ ] Test endpoint loading
- [ ] Start containers: `docker-compose up`
- [ ] Test queries in chatbot UI
- [ ] Monitor logs for errors
- [ ] Iterate on descriptions

### Key Files

```
chatbot-system/
├── backend/app/config/
│   ├── api_endpoints.yaml        ← YOUR CONFIGURATION
│   └── endpoint_loader.py         ← Loader (don't edit)
├── .env                           ← YOUR SECRETS
├── .env.example                   ← Template
└── docker-compose.yml
```

### Get Help

1. Read full guide: `ENDPOINT_CONFIGURATION_GUIDE.md`
2. Check logs: `docker-compose logs -f backend`
3. Enable debug: `LOG_LEVEL=DEBUG` in `.env`
4. Review examples in `api_endpoints.yaml`

---

**You're all set!** The chatbot will automatically understand and call your REST APIs based on natural language queries. No code required! 🎉
