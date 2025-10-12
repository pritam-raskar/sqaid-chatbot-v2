# SQAid Chatbot v2 - Railway Deployment Configuration

This document contains all the configuration details for the Railway-deployed chatbot system that your developer needs to integrate with their application.

## 🌐 Deployed URLs

### Backend Service
- **URL**: `https://sqaid-chatbot-v2-backend-production.up.railway.app`
- **API Base**: `https://sqaid-chatbot-v2-backend-production.up.railway.app/api/v1`
- **WebSocket**: `wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat`
- **Health Check**: `https://sqaid-chatbot-v2-backend-production.up.railway.app/health`

### Frontend Service
- **URL**: `https://sqaid-chatbot-v2-frontend-production.up.railway.app`

---

## 🔌 API Integration Guide

### 1. REST API Endpoints

#### Health Check
```bash
GET https://sqaid-chatbot-v2-backend-production.up.railway.app/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-10-07T12:00:00Z"
}
```

#### Chat Session Management
```bash
# Create new chat session
POST https://sqaid-chatbot-v2-backend-production.up.railway.app/api/v1/sessions

# Get session history
GET https://sqaid-chatbot-v2-backend-production.up.railway.app/api/v1/sessions/{session_id}
```

---

### 2. WebSocket Connection

#### Connection URL
```
wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat
```

#### Connection Example (JavaScript)
```javascript
const wsUrl = 'wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat';
const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log('Connected to chatbot');
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

socket.onerror = (error) => {
  console.error('WebSocket error:', error);
};

socket.onclose = () => {
  console.log('Disconnected from chatbot');
};
```

#### Message Format

**Sending a message:**
```json
{
  "type": "user_message",
  "content": "What is the status of case #12345?",
  "session_id": "optional-session-id",
  "context": {
    "page": "case_details",
    "case_id": "12345",
    "user_id": "user@example.com"
  }
}
```

**Receiving a message:**
```json
{
  "type": "bot_message",
  "content": "Case #12345 is currently in review status...",
  "session_id": "abc-123-def-456",
  "timestamp": "2025-10-07T12:00:00Z",
  "metadata": {
    "confidence": 0.95,
    "sources": ["postgresql", "rest_api"]
  }
}
```

#### Message Types

**User to Bot:**
- `user_message` - Regular chat message
- `context_update` - Update page context without sending message
- `session_end` - End current session

**Bot to User:**
- `bot_message` - Text response
- `bot_typing` - Typing indicator
- `bot_chart` - Chart visualization data
- `bot_error` - Error message
- `session_created` - New session confirmation

---

### 3. Environment Variables for Integration

If your developer is integrating the chatbot widget into their React app:

```bash
# Add to their .env file
VITE_CHATBOT_API_BASE_URL=https://sqaid-chatbot-v2-backend-production.up.railway.app
VITE_CHATBOT_WS_URL=wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat
VITE_CHATBOT_API_PREFIX=/api/v1
```

---

### 4. CORS Configuration

The backend is configured to accept requests from the following origins:

```json
[
  "https://sqaid-chatbot-v2-frontend-production.up.railway.app",
  "http://localhost:3000",
  "http://localhost:8080",
  "http://localhost:6001",
  "http://localhost:6002"
]
```

**If your developer needs to add their domain:**
1. Contact you to add their production domain to the CORS whitelist
2. The domain must be added to the `CORS_ORIGINS` environment variable in Railway
3. Backend service will need to be redeployed

---

### 5. Embedding the Chatbot Widget

#### Option A: Embed as iframe
```html
<iframe
  src="https://sqaid-chatbot-v2-frontend-production.up.railway.app"
  width="400"
  height="600"
  frameborder="0"
  style="position: fixed; bottom: 20px; right: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);"
></iframe>
```

#### Option B: Direct WebSocket Integration
```javascript
import React, { useEffect, useState } from 'react';

function ChatbotWidget() {
  const [socket, setSocket] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const ws = new WebSocket('wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat');

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [...prev, data]);
    };

    setSocket(ws);

    return () => ws.close();
  }, []);

  const sendMessage = (content) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: 'user_message',
        content: content,
        context: {
          page: window.location.pathname,
          // Add any relevant context from your app
        }
      }));
    }
  };

  return (
    // Your chat UI here
  );
}
```

---

### 6. Context Passing

The chatbot can receive context from the parent application to provide more relevant responses:

```javascript
// Send context when user navigates to a specific page
socket.send(JSON.stringify({
  type: 'context_update',
  context: {
    page: 'case_details',
    case_id: '12345',
    case_status: 'in_review',
    assigned_to: 'john.doe@example.com',
    priority: 'high'
  }
}));

// Then ask a question with that context
socket.send(JSON.stringify({
  type: 'user_message',
  content: 'What is the current status?',
  // Context is already set, chatbot will use it
}));
```

---

### 7. Data Sources Connected

The chatbot has access to the following data sources:

1. **PostgreSQL Database** (AWS RDS)
   - Database: `case_manager`
   - Host: `cais-db-main.clemsk88yp4y.us-east-1.rds.amazonaws.com`
   - Contains case management data

2. **LLM Provider**
   - Provider: Anthropic Claude
   - Models:
     - Execution Planner: `claude-3-5-haiku-20241022`
     - Tool Selector: `claude-3-5-haiku-20241022`
     - Response Formatter: `claude-3-5-sonnet-20241022`
     - Consolidator: `claude-3-5-sonnet-20241022`

3. **External APIs**
   - REST API endpoints (configurable)
   - SOAP services (configurable)

---

### 8. Features Available

#### ✅ Currently Enabled
- Natural language queries
- Database queries (PostgreSQL)
- Multi-source data aggregation
- Real-time WebSocket communication
- Streaming responses (tokens arrive as they're generated)
- Dynamic chart visualizations
- Context-aware responses
- Session management
- Message history

#### ⚠️ Configurable Features
These can be enabled by updating environment variables:

```bash
# Visualization Settings
ENABLE_VISUALIZATIONS=true
VISUALIZATION_MIN_DATA_POINTS=2
VISUALIZATION_MAX_DATA_POINTS=100

# Streaming Settings
ENABLE_LLM_STREAMING=true
LLM_STREAMING_CHUNK_SIZE=5

# LangGraph Orchestration
USE_LANGGRAPH=true
LANGGRAPH_ENABLE_PARALLEL=true
LANGGRAPH_ENABLE_CACHING=true
```

---

### 9. Example Queries

Here are some example queries the chatbot can handle:

```
User: "What is the status of case #12345?"
→ Queries database, returns case status

User: "Show me all high-priority cases assigned to John Doe"
→ Queries database, filters results, displays table

User: "What are the top 5 cases by severity this month?"
→ Queries database, aggregates data, shows chart

User: "Find cases created in the last 7 days"
→ Queries database with date filtering

User: "Compare case volumes between Q1 and Q2"
→ Multi-query aggregation, shows comparison chart
```

---

### 10. Authentication & Security

**Current Setup:**
- Backend is publicly accessible
- No authentication required for chatbot access
- CORS protection enabled

**If you need to add authentication:**
1. Contact you to enable JWT authentication
2. You'll need to configure:
   ```bash
   SECRET_KEY=your-secret-key
   JWT_ALGORITHM=HS256
   JWT_EXPIRATION_MINUTES=60
   ```
3. Developer will need to include JWT token in WebSocket connection:
   ```javascript
   const wsUrl = 'wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat?token=YOUR_JWT_TOKEN';
   ```

---

### 11. Rate Limiting

Current configuration:
```bash
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60  # seconds
```

This means: **100 requests per 60 seconds** per IP/session

---

### 12. Monitoring & Health Checks

#### Health Endpoint
```bash
curl https://sqaid-chatbot-v2-backend-production.up.railway.app/health
```

#### Metrics Available
- Connection status
- Active sessions
- Response times
- Error rates

**To access Railway logs:**
- Contact you for Railway dashboard access
- Logs are available in real-time

---

### 13. Support & Troubleshooting

#### Common Issues

**1. WebSocket Connection Failed**
```
Cause: CORS not configured for developer's domain
Solution: Add domain to CORS_ORIGINS in Railway
```

**2. Chatbot Not Responding**
```
Cause: Backend service might be restarting
Solution: Check health endpoint, wait 30 seconds for cold start
```

**3. Empty Responses**
```
Cause: Invalid message format or missing context
Solution: Ensure message follows the JSON schema above
```

#### Contact Information
- **Primary Contact**: You (Pritam)
- **Railway Dashboard**: https://railway.app (requires your login)
- **Repository**: Your GitHub repository

---

### 14. Testing Checklist for Developer

- [ ] Can connect to WebSocket URL
- [ ] Can send a test message
- [ ] Receives response from chatbot
- [ ] Can pass page context successfully
- [ ] Charts render correctly (if enabled)
- [ ] Session persists across page navigation
- [ ] Error handling works properly
- [ ] CORS allows requests from their domain

---

### 15. Quick Start Code Snippet

```javascript
// Complete working example
class ChatbotClient {
  constructor(wsUrl = 'wss://sqaid-chatbot-v2-backend-production.up.railway.app/ws/chat') {
    this.wsUrl = wsUrl;
    this.socket = null;
    this.sessionId = null;
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.socket = new WebSocket(this.wsUrl);

      this.socket.onopen = () => {
        console.log('✅ Connected to chatbot');
        resolve();
      };

      this.socket.onerror = (error) => {
        console.error('❌ Connection error:', error);
        reject(error);
      };

      this.socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      };
    });
  }

  handleMessage(data) {
    switch(data.type) {
      case 'session_created':
        this.sessionId = data.session_id;
        console.log('📝 Session created:', this.sessionId);
        break;
      case 'bot_message':
        console.log('🤖 Bot:', data.content);
        // Update your UI with the message
        break;
      case 'bot_chart':
        console.log('📊 Chart data:', data.chart_data);
        // Render chart in your UI
        break;
      case 'bot_error':
        console.error('⚠️ Error:', data.content);
        break;
    }
  }

  sendMessage(content, context = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.error('Not connected');
      return;
    }

    this.socket.send(JSON.stringify({
      type: 'user_message',
      content: content,
      session_id: this.sessionId,
      context: context
    }));
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
    }
  }
}

// Usage
const chatbot = new ChatbotClient();
await chatbot.connect();
chatbot.sendMessage('What cases are assigned to me?', {
  page: 'dashboard',
  user_id: 'john.doe@example.com'
});
```

---

## 📞 Need Help?

If your developer has any questions or needs:
- Additional CORS domains whitelisted
- Environment variables updated
- Features enabled/disabled
- Access to Railway logs
- Database schema information

**Contact you** to make these changes in the Railway dashboard.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-07
**Railway Project**: sqaid-chatbot-v2
