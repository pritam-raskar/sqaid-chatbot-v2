# Multi-Source Data Integration - Complete Guide

## Overview

Your chatbot now supports **intelligent multi-source data integration**, automatically combining data from REST APIs, SOAP services, and databases to answer complex queries.

## How It Works

### Example: "Show me the positions of the alerts"

```
User Query: "Show me the positions of the alerts"

Step 1: IntentRouter analyzes query
└─> Detects: Need data from multiple sources
    - "alerts" → REST API endpoint
    - "positions" → Oracle DB table

Step 2: Query Planner creates execution plan
└─> Plan:
    1. Call REST endpoint: get_alerts
    2. Extract alert IDs from response
    3. Query Oracle: SELECT * FROM positions WHERE alert_id IN (...)
    4. Merge results

Step 3: Tool Registry provides tools
└─> Available tools:
    - rest_get_alerts (REST API)
    - query_oracle (Database)

Step 4: LangChain Agent executes plan
└─> Agent reasoning:
    "I need to first get alerts, then query positions by alert IDs"

    Action 1: Use rest_get_alerts
    Result: [{"alert_id": "A1", ...}, {"alert_id": "A2", ...}]

    Action 2: Use query_oracle with alert_ids=[A1, A2]
    Result: [{"alert_id": "A1", "position": "...", ...}, ...]

Step 5: Response formatting
└─> "I found 2 alerts with their positions:
     1. Alert A1: Position X
     2. Alert A2: Position Y"
```

---

## Architecture Changes

### What Was Added

#### 1. Tool Initializer ([backend/app/intelligence/tool_initializer.py](chatbot-system/backend/app/intelligence/tool_initializer.py:1))

**Purpose:** Dynamically loads and registers ALL data sources as tools

**What it does:**
```python
# Reads api_endpoints.yaml
endpoint_loader = get_endpoint_loader()
endpoints = endpoint_loader.get_all_endpoints()

# Creates a tool for EACH endpoint
for endpoint in endpoints:
    tool = RESTAPITool(
        name=f"rest_{endpoint.name}",
        description=endpoint.description
    )
    tool_registry.register_tool(tool)

# Also registers Database tools
tool_registry.register_tool(DatabaseQueryTool(...))

# And SOAP tools if configured
tool_registry.register_tool(SOAPAPITool(...))
```

**Result:** All data sources available as tools in one registry

#### 2. Updated Main App ([backend/app/main.py](chatbot-system/backend/app/main.py:1))

**Changes:**
```python
# Added imports
from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.tool_initializer import initialize_tools

# Initialize on startup
tool_registry = ToolRegistry(embeddings=None)
tool_initializer = await initialize_tools(
    tool_registry=tool_registry,
    config_path=None  # Uses /config directory
)

# Pass to WebSocket handler
websocket_handler = WebSocketHandler(
    session_manager=session_manager,
    llm_provider=llm_provider,
    tool_registry=tool_registry  # ← All tools available
)
```

#### 3. Updated WebSocket Handler ([backend/app/orchestration/websocket_handler.py](chatbot-system/backend/app/orchestration/websocket_handler.py:1))

**Changes:**
```python
def __init__(self, session_manager, llm_provider=None, tool_registry=None):
    self.tool_registry = tool_registry

    # Initialize IntentRouter with tool registry
    if tool_registry:
        self.intent_router = IntentRouter(
            llm=llm_provider.get_langchain_llm(),
            tool_registry=tool_registry
        )
        # Agent now has access to ALL tools
        await self.intent_router.initialize_agent()
```

#### 4. IntentRouter Integration ([backend/app/intelligence/intent_router.py](chatbot-system/backend/app/intelligence/intent_router.py:1))

**Already implemented:**
```python
async def initialize_agent(self):
    # Get ALL tools from registry (REST, DB, SOAP)
    tools = self.tool_registry.get_all_tools()

    # Create LangChain agent with all tools
    self.agent = create_react_agent(
        llm=self.llm,
        tools=tools,  # ← Agent can use ANY tool
        prompt=prompt
    )
```

---

## Configuration

### Step 1: Configure REST Endpoints

**File:** `backend/app/config/api_endpoints.yaml`

```yaml
endpoints:
  - name: "get_alerts"
    description: "Get all alerts or search alerts by status, severity, type, or date range"
    url: "${BASE_URL}/api/v1/alerts"
    method: "GET"
    requires_auth: true
    parameters:
      - name: "status"
        type: "string"
        description: "Filter by status"
        required: false
        in: "query"
```

### Step 2: Configure Database Tables

**File:** Already handled by `DatabaseQueryTool`

The tool automatically discovers tables and creates descriptions:

```python
# In database_tool.py (already exists)
tool = DatabaseQueryTool(
    name="query_oracle",
    description="Query Oracle database for positions, alerts, cases, users, or other tables",
    db_type="oracle",
    db_config=oracle_config
)
```

### Step 3: Set Environment Variables

**File:** `.env`

```bash
# REST API Configuration
API_BASE_URL=https://your-api.example.com
API_AUTH_TOKEN=your_token_here

# Oracle Database Configuration
ORACLE_HOST=oracle.example.com
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=ORCL
ORACLE_USER=your_user
ORACLE_PASSWORD=your_password

# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password
```

---

## Real-World Examples

### Example 1: Alerts + Positions (Multi-Source)

**User:** "Show me the positions of all critical alerts"

**Execution:**
```
1. Agent calls: rest_get_alerts
   Parameters: {severity: "critical"}
   Result: [
     {alert_id: "A1", severity: "critical", ...},
     {alert_id: "A2", severity: "critical", ...}
   ]

2. Agent calls: query_oracle
   Query: "SELECT * FROM positions WHERE alert_id IN ('A1', 'A2')"
   Result: [
     {alert_id: "A1", latitude: 40.7, longitude: -74.0, ...},
     {alert_id: "A2", latitude: 34.0, longitude: -118.2, ...}
   ]

3. Agent merges results and formats response:
   "Found 2 critical alerts with positions:
    - Alert A1: Location (40.7, -74.0)
    - Alert A2: Location (34.0, -118.2)"
```

### Example 2: Cases + Users (Multi-Source)

**User:** "Show me all high priority cases and who's assigned to them"

**Execution:**
```
1. Agent calls: rest_search_cases
   Parameters: {priority: "high"}
   Result: [
     {case_id: "C1", assigned_to: "user_123"},
     {case_id: "C2", assigned_to: "user_456"}
   ]

2. Agent calls: query_postgresql
   Query: "SELECT * FROM users WHERE user_id IN ('user_123', 'user_456')"
   Result: [
     {user_id: "user_123", name: "John Doe", email: "john@..."},
     {user_id: "user_456", name: "Jane Smith", email: "jane@..."}
   ]

3. Agent merges and responds:
   "Found 2 high priority cases:
    - Case C1: Assigned to John Doe (john@...)
    - Case C2: Assigned to Jane Smith (jane@...)"
```

### Example 3: Pure REST API Query

**User:** "Show me all open cases"

**Execution:**
```
1. Agent detects: Only need REST API

2. Agent calls: rest_search_cases
   Parameters: {status: "open"}

3. Agent responds with results
```

### Example 4: Pure Database Query

**User:** "How many users are in the engineering department?"

**Execution:**
```
1. Agent detects: Only need database

2. Agent calls: query_postgresql
   Query: "SELECT COUNT(*) FROM users WHERE department = 'engineering'"

3. Agent responds: "There are 45 users in engineering"
```

---

## How the Agent Decides

The LangChain ReAct agent uses **reasoning** to choose tools:

### Decision Process

```
User: "Show me the positions of the alerts"

Agent Thought Process:
┌────────────────────────────────────────────────────┐
│ Thought: I need to find positions for alerts.     │
│          Positions likely require database query.  │
│          But I need alert IDs first from API.      │
│                                                    │
│ Action: Use rest_get_alerts to get alerts         │
│ Observation: Got 5 alerts with IDs                │
│                                                    │
│ Thought: Now I have alert IDs, I can query        │
│          positions table in database               │
│                                                    │
│ Action: Use query_oracle with alert_ids           │
│ Observation: Got position data                    │
│                                                    │
│ Thought: I have all data, can answer now          │
│                                                    │
│ Final Answer: [Formatted response]                │
└────────────────────────────────────────────────────┘
```

### Tool Selection Criteria

The agent considers:

1. **Tool Descriptions** - Semantic matching with query
2. **Available Parameters** - Does tool accept needed filters?
3. **Previous Results** - What data is already available?
4. **Query Context** - What's the user really asking for?

---

## Testing Multi-Source Queries

### Test 1: Verify Tools Loaded

```bash
cd chatbot-system/backend

python -c "
from app.intelligence.tool_registry import ToolRegistry
from app.intelligence.tool_initializer import initialize_tools
import asyncio

async def test():
    registry = ToolRegistry()
    await initialize_tools(registry)

    tools = registry.list_tools()
    print(f'Total tools: {len(tools)}')

    for tool in tools:
        print(f'  - {tool[\"name\"]} ({tool[\"data_source\"]})')
        print(f'    Description: {tool[\"description\"][:60]}...')

asyncio.run(test())
"
```

**Expected Output:**
```
Total tools: 12
  - rest_get_alerts (rest_api)
    Description: Get all alerts or search alerts by status, severity...
  - rest_search_cases (rest_api)
    Description: Search for cases by status, priority, assigned user...
  - query_oracle (oracle_db)
    Description: Query Oracle database for positions, alerts, cases...
  - query_postgresql (postgresql_db)
    Description: Query PostgreSQL database for users, sessions...
```

### Test 2: Test Individual Tools

```python
# Test REST tool
from app.intelligence.tools.api_tool import RESTAPITool

tool = RESTAPITool(base_url="http://api.example.com")
result = await tool._arun(
    endpoint="/api/v1/alerts",
    method="GET",
    params='{"status": "active"}'
)
print(result)

# Test Database tool
from app.intelligence.tools.database_tool import DatabaseQueryTool

tool = DatabaseQueryTool(
    db_type="oracle",
    db_config={...}
)
result = await tool._arun(
    table="positions",
    filters='{"alert_id": "A1"}'
)
print(result)
```

### Test 3: Test Full Integration

```bash
# Start the system
docker-compose up

# Test multi-source query via chatbot
# Open: http://localhost:3000
# Type: "Show me the positions of all critical alerts"
```

**Monitor logs:**
```bash
docker-compose logs -f backend | grep -E "(Tool|Agent|IntentRouter)"
```

**You should see:**
```
IntentRouter: Routing query to tools
Agent: Thought - Need to get alerts first
Agent: Action - rest_get_alerts
Agent: Observation - Got 5 alerts
Agent: Thought - Now get positions from DB
Agent: Action - query_oracle
Agent: Observation - Got position data
Agent: Final Answer - [Response]
```

---

## Troubleshooting

### Issue: "No tools registered"

**Cause:** Tool initializer failed to load

**Solution:**
```bash
# Check logs
docker-compose logs backend | grep "Tool"

# Verify config exists
ls -la backend/app/config/api_endpoints.yaml

# Test endpoint loader
python -c "from app.config import get_endpoint_loader; loader = get_endpoint_loader(); print(f'Loaded {len(loader.get_all_endpoints())} endpoints')"
```

### Issue: "Agent not using multiple tools"

**Cause:** Query might only need one source

**Solution:**
- Try more complex queries that clearly need both sources
- Check agent logs for reasoning
- Ensure endpoint/table descriptions mention relevant keywords

### Issue: "Tool execution failed"

**Cause:** Connection error to data source

**Solution:**
```bash
# Test REST API connection
curl -H "Authorization: Bearer $API_AUTH_TOKEN" $API_BASE_URL/api/v1/alerts

# Test Database connection
python -c "
from app.data_access.adapters.oracle_adapter import OracleAdapter
adapter = OracleAdapter(...)
await adapter.connect()
print('Connected')
"
```

---

## Summary

### What You Have Now

✅ **Single Tool Registry** - All data sources in one place
✅ **Dynamic Tool Loading** - From YAML config (no code changes)
✅ **Intelligent Routing** - LangChain agent chooses best tools
✅ **Multi-Source Queries** - Automatically combines REST + DB data
✅ **Semantic Matching** - Understands intent, not keywords
✅ **Zero Hardcoding** - All configuration-driven

### What Works Automatically

- ✅ "Show me the positions of the alerts" → REST + Oracle
- ✅ "Get all high priority cases with assignee details" → REST + PostgreSQL
- ✅ "List users in engineering department" → PostgreSQL only
- ✅ "Show me critical alerts" → REST only
- ✅ Any combination of data sources based on natural language

### Key Files

```
chatbot-system/
├── backend/app/
│   ├── config/
│   │   ├── api_endpoints.yaml          ← REST endpoint config
│   │   └── endpoint_loader.py          ← Loads endpoints
│   ├── intelligence/
│   │   ├── tool_registry.py            ← Central tool registry
│   │   ├── tool_initializer.py         ← NEW: Loads all tools
│   │   ├── intent_router.py            ← Routes to tools
│   │   └── tools/
│   │       ├── api_tool.py             ← REST API tool
│   │       ├── database_tool.py        ← Database tool
│   │       └── soap_api.py             ← SOAP tool
│   ├── orchestration/
│   │   └── websocket_handler.py        ← UPDATED: Uses tool registry
│   └── main.py                         ← UPDATED: Initializes tools
└── .env                                 ← Configuration
```

---

**Your chatbot now intelligently combines data from multiple sources!** 🎉

No additional configuration needed - just define your endpoints and the agent figures out how to combine them automatically.
