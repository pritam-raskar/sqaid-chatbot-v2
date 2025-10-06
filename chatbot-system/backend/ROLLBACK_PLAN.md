# Rollback Plan & Root Cause Analysis

## Changes to Rollback
1. Remove hardcoded system prompt from websocket_handler.py (lines 317-342)
2. Keep the logging line for debugging (line 351)

## Real Root Cause

The chatbot is NOT using tools! Here's why:

### Current Flow (BROKEN):
1. User asks: "How many alerts do we have?"
2. WebSocket handler calls `_handle_chat_message()`
3. Line 290: Checks for `intent_router` - **NOT AVAILABLE**
4. Falls back to line 312: Direct LLM call **WITHOUT TOOLS**
5. LLM has no context, no tools, no database access
6. LLM responds: "I cannot see any information..."

### What SHOULD Happen:
1. User asks: "How many alerts do we have?"
2. Intent router analyzes the query
3. Determines it needs database tool: `query_postgresql_cm_alerts`
4. Calls Anthropic with **TOOL DEFINITIONS** in the API call
5. Anthropic responds with tool_use block
6. System executes: `SELECT COUNT(*) FROM info_alert.cm_alerts`
7. Returns result to Anthropic
8. Anthropic formats: "There are 1,234 alerts in the system"

## The Real Problems:

### Problem 1: Tools Not Registered (0 tools initialized)
```
ERROR - Failed to register postgresql.cm_alerts: "DatabaseQueryTool" object has no field "_arun"
```
All tools fail because they're using old LangChain API without `_arun` method.

### Problem 2: No Tool Calling Integration
Even if tools were registered, the current code path (line 325) calls:
```python
response = await self.llm_provider.chat_completion(messages=messages, temperature=0.7)
```

This does NOT pass tools to Anthropic! Anthropic's tool calling requires:
```python
response = await client.messages.create(
    model="claude-3-5-haiku-20241022",
    messages=messages,
    tools=[...tool_definitions...],  # MISSING!
    max_tokens=4096
)
```

### Problem 3: No IntentRouter
Line 290 checks for `intent_router` but it's never initialized. The system should use an intelligent router to decide when to use tools.

## Correct Solution Path:

1. **Fix Tool Registration** - Update all tools to use proper async methods
2. **Implement Tool Calling** - Update Anthropic provider to support tool calling API
3. **Enable IntentRouter** - Route queries to appropriate tools
4. **Dynamic System Prompt** - Generate from available tools, NOT hardcoded
