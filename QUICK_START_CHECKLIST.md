# Quick Start Checklist - Multi-Source Chatbot

## ✅ Pre-Flight Checklist

### Required Files (All Present)
- [x] `backend/config/soap_endpoints.yaml`
- [x] `backend/config/database_schemas.yaml`
- [x] `backend/app/config/soap_endpoint_loader.py`
- [x] `backend/app/config/database_schema_loader.py`
- [x] `backend/app/intelligence/tool_initializer.py` (updated)
- [x] `backend/Dockerfile`
- [x] `backend/validate_setup.py`

### Dependencies (All in requirements.txt)
- [x] pyyaml==6.0.1
- [x] pydantic==2.5.3
- [x] langchain==0.1.0
- [x] zeep==4.2.1 (SOAP)
- [x] oracledb==2.0.0
- [x] asyncpg==0.29.0

---

## 🚀 Start Commands

### Option 1: Start with defaults (REST + PostgreSQL only)

```bash
cd chatbot-system
docker-compose up --build
```

### Option 2: Start with full configuration (REST + SOAP + Oracle + PostgreSQL)

```bash
# 1. Create .env file
cd chatbot-system
cat > .env << 'EOF'
# REST API
API_BASE_URL=http://your-api.com
API_AUTH_TOKEN=your_token

# SOAP (optional)
SOAP_WSDL_URL=http://your-soap.com/service?wsdl
SOAP_AUTH_USERNAME=username
SOAP_AUTH_PASSWORD=password

# Oracle (optional)
ORACLE_HOST=oracle.host.com
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=ORCL
ORACLE_USER=user
ORACLE_PASSWORD=password

# PostgreSQL (from docker-compose)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=chatbot_db
POSTGRES_USER=chatbot_user
POSTGRES_PASSWORD=chatbot_password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# LLM Provider
LLM_PROVIDER=eliza
ELIZA_API_URL=http://localhost:5000
EOF

# 2. Start services
docker-compose up --build
```

---

## 🔍 Verification Steps

### Step 1: Check if services started

```bash
docker-compose ps
```

Expected output:
```
chatbot-backend    running
chatbot-postgres   running
chatbot-redis      running
chatbot-frontend   running
```

### Step 2: Check tool registration logs

```bash
docker-compose logs backend | grep -E "(Registered|initialized)"
```

Expected output:
```
✓ Registered REST endpoint tool: search_cases
✓ Registered SOAP endpoint tool: get_customer_details
✓ Registered DB table tool: oracle.alert_positions
✓ Registered DB table tool: postgresql.users
✓ Successfully initialized 19 tools
```

### Step 3: Run validation script

```bash
docker-compose exec backend python validate_setup.py
```

Expected output:
```
✓ PASS - YAML Validity
✓ PASS - Python Imports
✓ PASS - Configuration Loaders
✓ PASS - Tool Initializer

✓ ALL TESTS PASSED - Ready to start service!
```

---

## 🧪 Test Queries

Open browser: `http://localhost:3000`

### Test 1: REST API
```
"Show me all open cases"
```

### Test 2: Database
```
"How many users are there?"
```

### Test 3: Multi-Source (REST + DB)
```
"Show me high priority cases and who they're assigned to"
```

### Test 4: Multi-Source (DB + DB)
```
"Show me alert positions"
```

### Test 5: SOAP (if configured)
```
"Get customer details for customer 12345"
```

---

## 📊 Expected Tool Count

| Data Source | Tool Count | Configured? |
|-------------|------------|-------------|
| REST API | 9 | ✅ Yes (default) |
| SOAP API | 3 | ⚠️ Needs WSDL URL |
| Oracle DB | 3 | ⚠️ Needs connection |
| PostgreSQL | 4 | ✅ Yes (docker-compose) |
| **Total** | **19** | **Minimum: 13** |

---

## 🐛 Troubleshooting

### Problem: "No tools registered"

**Solution:**
```bash
docker-compose logs backend | grep ERROR
docker-compose restart backend
```

### Problem: "SOAP endpoints not loading"

**Solution:**
```bash
# Add to .env:
SOAP_WSDL_URL=http://your-soap-url
docker-compose restart backend
```

### Problem: "Import errors"

**Solution:**
```bash
docker-compose down
docker-compose up --build
```

### Problem: "YAML parsing errors"

**Solution:**
```bash
# Validate YAML
python3 -c "import yaml; yaml.safe_load(open('backend/config/soap_endpoints.yaml'))"
```

---

## 📝 Adding New Endpoints/Tables

### Add REST Endpoint

Edit: `backend/app/config/api_endpoints.yaml`

```yaml
- name: "my_new_endpoint"
  description: "What it does with keywords"
  url: "${BASE_URL}/api/my-endpoint"
  method: "GET"
  parameters: [...]
```

Restart: `docker-compose restart backend`

### Add SOAP Operation

Edit: `backend/config/soap_endpoints.yaml`

```yaml
- name: "my_soap_operation"
  description: "What it does with keywords"
  wsdl_url: "${SOAP_WSDL_URL}"
  operation: "MyOperation"
  parameters: [...]
```

Restart: `docker-compose restart backend`

### Add Database Table

Edit: `backend/config/database_schemas.yaml`

```yaml
- name: "my_table"
  description: "What it contains with keywords"
  keywords: ["keyword1", "keyword2"]
  primary_key: "id"
  searchable_columns: [...]
```

Restart: `docker-compose restart backend`

---

## ✅ Success Indicators

You know it's working when:

1. ✅ Logs show "Successfully initialized X tools" (X ≥ 13)
2. ✅ No ERROR messages in logs
3. ✅ Frontend loads at http://localhost:3000
4. ✅ Chatbot responds to queries
5. ✅ Agent calls appropriate tools based on query

---

## 🎯 Quick Reference

| Command | Purpose |
|---------|---------|
| `docker-compose up --build` | Start all services |
| `docker-compose logs -f backend` | Watch backend logs |
| `docker-compose exec backend python validate_setup.py` | Validate setup |
| `docker-compose restart backend` | Restart after config changes |
| `docker-compose down` | Stop all services |

---

## 📚 Documentation

- [IMPLEMENTATION_PLAN_SOAP_DB.md](IMPLEMENTATION_PLAN_SOAP_DB.md) - Full implementation details
- [IMPLEMENTATION_REVIEW.md](IMPLEMENTATION_REVIEW.md) - Code review and verification
- [ENDPOINT_CONFIGURATION_GUIDE.md](ENDPOINT_CONFIGURATION_GUIDE.md) - REST endpoint guide
- [MULTI_SOURCE_INTEGRATION.md](MULTI_SOURCE_INTEGRATION.md) - Multi-source architecture

---

**Everything is ready! Start the service and test multi-source queries!** 🚀
