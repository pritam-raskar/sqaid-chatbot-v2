# REST Endpoint Architecture - How It Works

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                             │
│                    (React Frontend - Port 3000)                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        WEBSOCKET HANDLER                             │
│                  (Real-time bidirectional communication)             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        INTELLIGENCE LAYER                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     INTENT ROUTER                            │  │
│  │          (LangChain ReAct Agent - Zero-shot)                 │  │
│  │  • Analyzes user query                                       │  │
│  │  • Determines intent (search, create, update, etc.)          │  │
│  │  • Extracts entities (case IDs, statuses, priorities)        │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  SEMANTIC MATCHER                            │  │
│  │           (Embedding-based similarity search)                │  │
│  │  • Loads endpoint configurations                             │  │
│  │  • Compares query with endpoint descriptions                 │  │
│  │  • Returns best matching endpoints                           │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    QUERY PLANNER                             │  │
│  │              (Multi-step query orchestration)                │  │
│  │  • Decomposes complex queries                                │  │
│  │  • Builds dependency graph                                   │  │
│  │  • Plans execution order                                     │  │
│  │  • Handles multi-step workflows                              │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                                │                                     │
│                                ▼                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  ENDPOINT LOADER                             │  │
│  │          (YAML configuration → Python objects)               │  │
│  │  • Reads api_endpoints.yaml                                  │  │
│  │  • Parses endpoint definitions                               │  │
│  │  • Loads authentication config                               │  │
│  │  • Replaces ${BASE_URL} placeholders                         │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────────┼─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         TOOL REGISTRY                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │  REST API    │  │ Database     │  │  SOAP API    │             │
│  │  Tool        │  │ Tool         │  │  Tool        │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                  │                  │                      │
└─────────┼──────────────────┼──────────────────┼──────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA ACCESS LAYER                               │
│  ┌───────────────┐  ┌────────────────┐  ┌────────────────┐         │
│  │ REST Adapter  │  │ PostgreSQL     │  │ SOAP Adapter   │         │
│  │               │  │ Adapter        │  │                │         │
│  └───────┬───────┘  └───────┬────────┘  └───────┬────────��         │
└──────────┼──────────────────┼───────────────────┼──────────────────┘
           │                  │                   │
           ▼                  ▼                   ▼
┌──────────────────┐ ┌───────────────┐ ┌──────────────────┐
│  YOUR REST API   │ │  PostgreSQL   │ │  SOAP Service    │
│  (Your backend)  │ │  Database     │ │  (Legacy)        │
└──────────────────┘ └───────────────┘ └──────────────────┘
```

---

## Request Flow Example

### Example Query: "Show me all high priority cases assigned to John"

```
Step 1: USER INPUT
└─> User types in chat: "Show me all high priority cases assigned to John"

Step 2: WEBSOCKET HANDLER
└─> Receives message via WebSocket
    └─> Forwards to Intent Router

Step 3: INTENT ROUTER (LangChain ReAct Agent)
└─> Analysis:
    • Intent: SEARCH/QUERY
    • Entity: CASES
    • Filters detected:
      - priority = "high"
      - assignee = "John"

Step 4: SEMANTIC MATCHER
└─> Loads endpoint definitions from api_endpoints.yaml
└─> Compares query with descriptions:

    Endpoint: "search_cases"
    Description: "Search for cases by status, priority, assignee..."
    Similarity Score: 0.92 ✅ HIGH MATCH

    Endpoint: "get_user_info"
    Description: "Get user information by ID or email"
    Similarity Score: 0.15 ❌ LOW MATCH

└─> Returns: "search_cases" endpoint

Step 5: ENDPOINT LOADER
└─> Retrieves full endpoint definition:
    {
      "name": "search_cases",
      "url": "http://api.example.com/api/v1/cases/search",
      "method": "POST",
      "parameters": [
        {"name": "priority", "in": "body"},
        {"name": "assigned_to", "in": "body"}
      ]
    }

Step 6: QUERY PLANNER
└─> Plans execution:
    • Single-step query (no dependencies)
    • Parameters to send:
      {
        "priority": "high",
        "assigned_to": "John"
      }

Step 7: REST API TOOL
└─> Executes API call:
    POST http://api.example.com/api/v1/cases/search
    Headers:
      Authorization: Bearer <token>
      Content-Type: application/json
    Body:
      {
        "priority": "high",
        "assigned_to": "John"
      }

Step 8: REST ADAPTER
└─> Makes HTTP request to your API
└─> Receives response:
    [
      {"case_id": "123", "title": "Server Down", "priority": "high", ...},
      {"case_id": "456", "title": "Bug Fix", "priority": "high", ...}
    ]

Step 9: RESPONSE FORMATTING
└─> Formats response for LLM:
    "Found 2 high priority cases assigned to John:
     1. Case #123: Server Down
     2. Case #456: Bug Fix"

Step 10: WEBSOCKET HANDLER
└─> Sends formatted response back to user via WebSocket

Step 11: USER INTERFACE
└─> Displays response in chat:
    "I found 2 high priority cases assigned to John:
     1. Case #123: Server Down
     2. Case #456: Bug Fix"
```

---

## Configuration Flow

### How Endpoint Configuration Works

```
┌─────────────────────────────────────────────────────────────────┐
│                 api_endpoints.yaml                               │
│                                                                  │
│  endpoints:                                                      │
│    - name: "search_cases"                                        │
│      description: "Search for cases by status, priority..."      │
│      url: "${BASE_URL}/api/v1/cases/search"                      │
│      method: "POST"                                              │
│      parameters:                                                 │
│        - name: "priority"                                        │
│          in: "body"                                              │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Loaded at startup
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ENDPOINT LOADER                                 │
│  (backend/app/config/endpoint_loader.py)                         │
│                                                                  │
│  1. Reads YAML file                                              │
│  2. Validates syntax                                             │
│  3. Loads environment variables                                  │
│     • Replaces ${BASE_URL} with API_BASE_URL env var            │
│  4. Parses into Python objects (Pydantic models)                 │
│  5. Caches endpoint definitions in memory                        │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Used at runtime
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ENDPOINT DEFINITION (in memory)                     │
│                                                                  │
│  EndpointDefinition(                                             │
│    name="search_cases",                                          │
│    description="Search for cases by status, priority...",        │
│    url="http://api.example.com/api/v1/cases/search",            │
│    method="POST",                                                │
│    requires_auth=True,                                           │
│    parameters=[                                                  │
│      EndpointParameter(name="priority", in_="body", ...),        │
│      EndpointParameter(name="status", in_="body", ...)           │
│    ]                                                             │
│  )                                                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Queried by
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SEMANTIC MATCHER                               │
│                                                                  │
│  get_endpoints_by_description("find high priority cases")        │
│    └─> Returns matching endpoints based on similarity           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Intent Router
**Location:** `backend/app/intelligence/intent_router.py`

**Responsibilities:**
- Analyze user query using LangChain ReAct agent
- Determine user intent (search, create, update, delete, etc.)
- Extract entities (case IDs, user names, dates, etc.)
- Extract filter criteria (status=open, priority=high)
- Route to appropriate tool/endpoint

**Example Input:** "Show me critical bugs from last week"

**Example Output:**
```python
{
  "intent": "search",
  "entity_type": "cases",
  "filters": {
    "priority": "critical",
    "date_from": "2024-09-24",
    "date_to": "2024-10-01"
  }
}
```

### 2. Semantic Matcher
**Location:** `backend/app/intelligence/semantic_matcher.py`

**Responsibilities:**
- Load endpoint definitions from EndpointLoader
- Use embeddings to compute semantic similarity
- Match user query against endpoint descriptions
- Return ranked list of matching endpoints
- No hardcoding - purely semantic

**Example Input:**
```python
query = "find high priority bugs"
```

**Example Output:**
```python
[
  EndpointDefinition(name="search_cases", similarity=0.92),
  EndpointDefinition(name="get_statistics", similarity=0.34),
  ...
]
```

### 3. Query Planner
**Location:** `backend/app/intelligence/query_planner.py`

**Responsibilities:**
- Decompose complex multi-step queries
- Build dependency graph
- Determine execution order (topological sort)
- Execute queries in parallel where possible
- Merge results from multiple endpoints

**Example Input:** "Show me all critical cases and their assigned users"

**Example Plan:**
```python
{
  "steps": [
    {
      "id": "step1",
      "endpoint": "search_cases",
      "params": {"priority": "critical"},
      "dependencies": []
    },
    {
      "id": "step2",
      "endpoint": "get_user_info",
      "params": {"user_id": "<from step1>"},
      "dependencies": ["step1"]
    }
  ]
}
```

### 4. Endpoint Loader
**Location:** `backend/app/config/endpoint_loader.py`

**Responsibilities:**
- Load YAML configuration file
- Parse endpoint definitions
- Replace environment variable placeholders
- Validate configuration
- Provide query methods (get_endpoint, get_all_endpoints, etc.)
- Build authentication headers

**Example Usage:**
```python
from app.config import get_endpoint_loader

loader = get_endpoint_loader()
endpoint = loader.get_endpoint("search_cases")
headers = loader.build_headers()
```

### 5. REST API Tool
**Location:** `backend/app/intelligence/tools/api_tool.py`

**Responsibilities:**
- Execute REST API calls (GET, POST, PUT, DELETE)
- Format parameters based on `in` field (path, query, body, header)
- Add authentication headers
- Handle retries and timeouts
- Format responses for LLM consumption
- Error handling and logging

**Example Usage:**
```python
tool = RESTAPITool(base_url="http://api.example.com")
result = await tool._arun(
    endpoint="/api/v1/cases/search",
    method="POST",
    body='{"priority": "high"}'
)
```

### 6. REST Adapter
**Location:** `backend/app/data_access/adapters/rest_adapter.py`

**Responsibilities:**
- Low-level HTTP client (aiohttp)
- Connection pooling
- Retry logic
- Timeout handling
- Response parsing
- Error handling

---

## Data Flow Diagram

### Simple Query Flow

```
User: "Show me open cases"
  │
  ├─> Intent Router
  │     └─> Intent: SEARCH, Entity: CASES, Filter: status=open
  │
  ├─> Semantic Matcher
  │     └─> Match: "search_cases" (similarity: 0.95)
  │
  ├─> Endpoint Loader
  │     └─> Load: search_cases definition
  │
  ├─> Query Planner
  │     └─> Plan: Single-step query
  │
  ├─> REST API Tool
  │     └─> Call: POST /api/v1/cases/search
  │           Body: {"status": "open"}
  │
  ├─> REST Adapter
  │     └─> HTTP: POST https://api.example.com/api/v1/cases/search
  │
  ├─> Your API
  │     └─> Returns: [{"case_id": "123", ...}, ...]
  │
  ├─> Format Response
  │     └─> "Found 5 open cases: ..."
  │
  └─> User sees: "Found 5 open cases:
                  1. Case #123: Server Down
                  2. Case #456: Bug Fix
                  ..."
```

### Multi-Step Query Flow

```
User: "Show me all critical cases and who's assigned to them"
  │
  ├─> Intent Router
  │     └─> Complex query detected
  │
  ├─> Query Planner
  │     ├─> Step 1: search_cases (priority=critical)
  │     └─> Step 2: get_user_info (for each assignee from step 1)
  │
  ├─> Execute Step 1
  │     ├─> Call: search_cases
  │     └─> Result: [
  │           {"case_id": "123", "assigned_to": "user_1"},
  │           {"case_id": "456", "assigned_to": "user_2"}
  │         ]
  │
  ├─> Execute Step 2 (in parallel)
  │     ├─> Call: get_user_info(user_1)
  │     ├─> Call: get_user_info(user_2)
  │     └─> Results: [
  │           {"user_id": "user_1", "name": "John"},
  │           {"user_id": "user_2", "name": "Jane"}
  │         ]
  │
  ├─> Merge Results
  │     └─> Combine case and user data
  │
  └─> User sees: "Found 2 critical cases:
                  1. Case #123: Server Down (John)
                  2. Case #456: Bug Fix (Jane)"
```

---

## Key Design Principles

### 1. **Configuration Over Code**
- Endpoints defined in YAML, not Python code
- No redeployment needed for new endpoints
- Easy for non-developers to configure

### 2. **Semantic Matching**
- No hardcoded if-else logic
- Uses embedding similarity
- Automatically finds best endpoint
- Handles synonyms and variations

### 3. **Intelligent Routing**
- LangChain ReAct agent for reasoning
- Zero-shot learning (no training needed)
- Handles complex multi-turn conversations
- Contextual awareness

### 4. **Modular Architecture**
- Each component has single responsibility
- Easy to test in isolation
- Easy to extend or replace
- Clear interfaces between layers

### 5. **Async/Await Throughout**
- Non-blocking I/O
- Handles many concurrent users
- Parallel query execution
- Efficient resource usage

---

## Environment Variables Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         .env file                                │
│                                                                  │
│  API_BASE_URL=https://api.example.com                            │
│  API_AUTH_TOKEN=eyJhbGciOiJIUzI1NiIs...                          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Loaded by Docker Compose
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Environment Variables (Runtime)                     │
│  process.env.API_BASE_URL = "https://api.example.com"            │
│  process.env.API_AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIs..."          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Used by
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ENDPOINT LOADER                                │
│                                                                  │
│  1. Reads API_BASE_URL from env                                  │
│  2. Replaces ${BASE_URL} in YAML:                                │
│     "${BASE_URL}/api/cases" → "https://api.example.com/api/cases"│
│                                                                  │
│  3. Reads API_AUTH_TOKEN from env                                │
│  4. Builds auth headers:                                         │
│     {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIs..."}          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            │ Passed to
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REST API TOOL                                 │
│  Uses headers for every API call                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Summary

The chatbot architecture uses a **layered, intelligent approach** to automatically identify and call your REST APIs:

1. **User queries** are analyzed for intent and entities
2. **Semantic matching** finds the best endpoint from YAML config
3. **Query planning** handles complex multi-step scenarios
4. **REST tools** execute the actual API calls
5. **Responses** are formatted and returned to user

**Zero hardcoding** - everything is configuration-driven and semantically matched!








Intelligent Multi-Source Decision Making
How the System Will Work
User Query: "Show me positions of critical alerts from last week"

LangChain Agent Reasoning:
┌─────────────────────────────────────────────────┐
│ Step 1: Analyze Query                          │
│ - Need: "alerts" with severity "critical"      │
│ - Need: "positions" (geographic data)          │
│ - Filter: "last week" (date range)             │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Step 2: Semantic Tool Matching                 │
│                                                 │
│ Available Tools (with descriptions):           │
│                                                 │
│ ✓ rest_get_alerts                              │
│   "Get alerts by severity, type, status..."    │
│   Match Score: 0.92 → HIGH                     │
│                                                 │
│ ✓ query_oracle_alert_positions                 │
│   "Geographic positions of security alerts..." │
│   Match Score: 0.89 → HIGH                     │
│                                                 │
│ ✗ query_postgresql_users                       │
│   "User accounts, profiles..."                 │
│   Match Score: 0.12 → LOW (irrelevant)         │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Step 3: Agent Creates Plan                     │
│                                                 │
│ Thought: "I need alerts AND positions"         │
│                                                 │
│ Plan:                                           │
│ 1. Call rest_get_alerts                        │
│    params: {severity: "critical",              │
│             date_from: "2025-09-24"}           │
│                                                 │
│ 2. Extract alert_ids from response             │
│                                                 │
│ 3. Call query_oracle_alert_positions           │
│    filters: alert_id IN (extracted_ids)        │
│                                                 │
│ 4. Merge results and format response           │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Step 4: Execute Autonomously                   │
│                                                 │
│ Action 1: rest_get_alerts                      │
│ → Returns: [{alert_id: "A1"}, {alert_id: "A2"}]│
│                                                 │
│ Action 2: query_oracle_alert_positions         │
│ → Returns: [{alert_id: "A1", lat: 40.7, ...}] │
│                                                 │
│ Final Answer: "Found 2 critical alerts..."     │
└─────────────────────────────────────────────────┘
Key Intelligence Features
1. Semantic Understanding
The agent uses descriptions to understand what each data source contains:
# REST endpoint
description: "Get alerts by severity, type, status..."
→ Agent knows: "Use this for alert data"

# Database table
description: "Geographic positions of security alerts..."
→ Agent knows: "Use this for location data"
2. Autonomous Routing
You don't configure routing logic! The agent decides:
Query: "Show me John's high priority cases"

Agent Reasoning:
- "John" → Need user data
- "cases" → Need case data
- Checks tool descriptions...
- Finds: rest_search_cases (mentions "cases, tickets...")
- Finds: query_postgresql_users (mentions "user, person...")
- Decision: Use BOTH tools
- Execute: Get user ID for John → Search cases by assignee
3. Dynamic Multi-Step Planning
The agent can chain multiple data sources automatically: Example 1: REST + Database
User: "Show customers who made payments over $1000"

Agent Plan:
1. soap_get_customers → Get all customers
2. query_oracle_payments WHERE amount > 1000 → Get payment records
3. Match customer_ids → Merge results
Example 2: Database + Database
User: "Show users with pending notifications"

Agent Plan:
1. query_postgresql_notifications WHERE status = 'pending'
2. Extract user_ids
3. query_postgresql_users WHERE user_id IN (...)
4. Merge and return
Example 3: REST + SOAP + Database (3-way!)
User: "Show me cases assigned to validated customers with alert positions"

Agent Plan:
1. rest_search_cases → Get all cases
2. Extract customer_ids from cases
3. soap_validate_account (for each customer) → Check if valid
4. Filter to valid customers only
5. query_oracle_alert_positions WHERE case_id IN (...) → Get positions
6. Merge all three data sources
What Makes It "Smart"
No Hardcoding Required
❌ OLD WAY (Hardcoded):
if query.contains("alerts") and query.contains("positions"):
    alerts = call_rest_api("/alerts")
    positions = query_database("alert_positions")
    return merge(alerts, positions)
✅ NEW WAY (Autonomous):
# Just provide descriptions
rest_get_alerts:
  description: "Get security alerts..."

query_oracle_alert_positions:
  description: "Geographic positions of alerts..."

# Agent figures out the rest!
Handles New Combinations Automatically
Without any code changes:
User: "Show me incidents with audit logs"
→ Agent: Combines query_oracle_incidents + query_oracle_audit_logs

User: "Get customer details and their payment history"
→ Agent: Combines soap_get_customer_details + query_oracle_payments

User: "Show cases with user info and notifications"
→ Agent: Combines rest_search_cases + query_postgresql_users + query_postgresql_notifications
Learns From Descriptions
The better your descriptions, the smarter the agent:
# GOOD description
description: "Geographic positions of security alerts including latitude, longitude, timestamp. Use when user asks about alert locations, where alerts occurred, or coordinates."

# Agent understands ALL these queries:
- "Where did alerts happen?"
- "Show me alert coordinates"
- "What's the location of alert A123?"
- "Map the alerts"
Real-World Scenarios
Scenario 1: Data Discovery
User asks something new you never configured:
User: "Show me high priority cases in engineering department"

Agent Reasoning:
- Searches ALL tool descriptions
- Finds: rest_search_cases (has "priority" in description)
- Finds: query_postgresql_users (has "department" in description)
- Decision: Get engineering users → Filter cases by those users
- Executes automatically
Scenario 2: Optimization
Agent chooses the most efficient source:
User: "How many users are there?"

Option 1: rest_list_users → Fetch all, count in memory
Option 2: query_postgresql_users → SELECT COUNT(*) (faster!)

Agent Decision:
- Sees "database" tool has "aggregate_data" capability
- Chooses database for counting (more efficient)
Scenario 3: Fallback
If one source fails, tries alternatives:
User: "Get case #12345"

Agent Tries:
1. rest_get_case_details → Connection timeout
2. Agent: "Let me try database"
3. query_postgresql_cases WHERE case_id = '12345' → Success!
The Magic Formula
Semantic Descriptions
    +
LangChain ReAct Agent (reasoning)
    +
Tool Registry (all data sources)
    +
Zero-shot Learning
    =
AUTONOMOUS DATA INTEGRATION
No routing code, no if-statements, no hardcoded logic!
What You Control
You ONLY provide:
✅ Descriptions - What each data source contains
✅ Keywords - Terms users might use
✅ Parameters - What filters are available
The agent handles:
🤖 Which sources to use
🤖 In what order
🤖 How to combine results
🤖 When to use multiple sources
🤖 How to extract and pass IDs between sources
Answer: YES!
After implementation, your system will: ✅ Automatically decide which data sources to query
✅ Combine multiple sources intelligently
✅ Handle queries you never anticipated
✅ Learn from semantic descriptions
✅ Work without routing code
✅ Scale to any number of data sources Just add configuration → Agent figures out the rest! 🚀