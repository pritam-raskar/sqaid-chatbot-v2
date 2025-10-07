# Railway Deployment Guide

This guide explains how to deploy the SQAid Chatbot v2 system to Railway.com.

## Prerequisites

1. GitHub account with this repository
2. Railway.com account (sign up at https://railway.app)
3. Required API keys (Eliza/OpenAI/Anthropic)

## Deployment Steps

### Step 1: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Click "Login" and authenticate with GitHub
3. Authorize Railway to access your repositories

### Step 2: Create New Project

1. Click **"New Project"** in Railway dashboard
2. Select **"Empty Project"**
3. Name it: `sqaid-chatbot-v2`

### Step 3: Add PostgreSQL Database

1. In your project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway will automatically create and configure PostgreSQL
4. Note: Connection details are auto-configured via environment variables

### Step 4: Add Redis Database

1. Click **"+ New"** again
2. Select **"Database"** → **"Redis"**
3. Railway will automatically create and configure Redis
4. Note: Connection details are auto-configured via environment variables

### Step 5: Deploy Backend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select your chatbot repository
3. Railway will detect the repository
4. Click **"Add Variables"** and configure:

#### Required Environment Variables for Backend:

```bash
# Application
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=$PORT
DEBUG=false

# LLM Provider (Choose one or more)
# Option 1: Eliza
ELIZA_CERT_PATH=/path/to/cert
ELIZA_PRIVATE_KEY_PATH=/path/to/key
ELIZA_ENV=QA
ELIZA_DEFAULT_MODEL=llama-3.3

# Option 2: OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Option 3: Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Database (Auto-configured by Railway)
POSTGRES_HOST=${{Postgres.PGHOST}}
POSTGRES_PORT=${{Postgres.PGPORT}}
POSTGRES_DB=${{Postgres.PGDATABASE}}
POSTGRES_USER=${{Postgres.PGUSER}}
POSTGRES_PASSWORD=${{Postgres.PGPASSWORD}}

# Redis (Auto-configured by Railway)
REDIS_HOST=${{Redis.REDIS_HOST}}
REDIS_PORT=${{Redis.REDIS_PORT}}
REDIS_PASSWORD=${{Redis.REDIS_PASSWORD}}

# External APIs (Configure based on your needs)
REST_API_BASE_URL=https://your-api.com
REST_API_KEY=your-api-key
SOAP_WSDL_URL=http://your-soap.com/service?wsdl

# Security
SECRET_KEY=your-production-secret-key-change-this
JWT_ALGORITHM=HS256

# CORS (Update with your frontend URL after deployment)
CORS_ORIGINS=["https://your-frontend.railway.app"]
```

5. Click **"Settings"** → **"Root Directory"** → Set to: `chatbot-system/backend`
6. Click **"Deploy"**

### Step 6: Deploy Frontend Service

1. Click **"+ New"** → **"GitHub Repo"**
2. Select the same repository (yes, again)
3. Click **"Settings"** → **"Root Directory"** → Set to: `chatbot-system/frontend`
4. Configure environment variables:

```bash
# Backend URL (Update after backend is deployed)
VITE_API_URL=https://your-backend.railway.app
VITE_WS_URL=wss://your-backend.railway.app
```

5. Click **"Deploy"**

### Step 7: Configure Custom Domains (Optional)

1. Click on **Backend service** → **"Settings"** → **"Networking"**
2. Click **"Generate Domain"** or add custom domain
3. Copy the backend URL
4. Click on **Frontend service** → **"Variables"**
5. Update `VITE_API_URL` and `VITE_WS_URL` with backend URL
6. Redeploy frontend
7. Generate domain for frontend or add custom domain

### Step 8: Update CORS Settings

1. Go to Backend service → **"Variables"**
2. Update `CORS_ORIGINS` to include your frontend URL
3. Redeploy backend

### Step 9: Verify Deployment

1. Open frontend URL in browser
2. Test chat functionality
3. Check backend logs in Railway dashboard
4. Verify database connections

## Auto-Deploy Configuration

Railway automatically deploys when you push to your main branch.

To configure:
1. Go to **Backend/Frontend service** → **"Settings"** → **"Source"**
2. Set **"Branch"** to `main`
3. Enable **"Auto-deploy"**

Now every push to `main` will trigger automatic deployment!

## Monitoring and Logs

- **View Logs:** Click on service → **"Deployments"** → Select deployment
- **Metrics:** Click on service → **"Metrics"** to see CPU/RAM usage
- **Database:** Click on PostgreSQL/Redis to see connection info and metrics

## Cost Estimation

Based on Hobby tier ($5/month minimum):

- **Backend:** ~$3-5/month (1-2 GB RAM, 1 vCPU)
- **Frontend:** ~$1-2/month (512 MB RAM)
- **PostgreSQL:** ~$2-3/month (1 GB RAM)
- **Redis:** ~$1-2/month (256 MB RAM)

**Total estimated:** $10-15/month for light usage

## Troubleshooting

### Build Failures

1. Check build logs in Railway dashboard
2. Verify Dockerfile paths are correct
3. Ensure all dependencies are in requirements.txt/package.json

### Connection Issues

1. Verify environment variables are set correctly
2. Check database connection strings
3. Ensure CORS_ORIGINS includes frontend URL

### Frontend Can't Reach Backend

1. Update VITE_API_URL and VITE_WS_URL
2. Redeploy frontend after updating
3. Check backend is running and accessible

## Security Best Practices

1. **Never commit API keys** - Use Railway environment variables
2. **Use strong SECRET_KEY** - Generate random string for production
3. **Enable HTTPS** - Railway provides automatic SSL
4. **Restrict CORS** - Only allow your frontend domain
5. **Monitor logs** - Check for suspicious activity

## Scaling

Railway auto-scales based on resource usage. To manually configure:

1. Go to service → **"Settings"** → **"Resources"**
2. Adjust CPU/RAM limits
3. Monitor costs in **"Usage"** tab

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- GitHub Issues: Create issue in this repository
