# Backend Dockerfile for Chatbot System

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding .env via .dockerignore)
COPY . .

# Verify no .env file was copied (debug)
RUN echo "Checking for .env file..." && ls -la .env 2>&1 || echo ".env not found (good!)"

# Verify Railway env vars are available
RUN echo "ANTHROPIC_API_KEY length: $(echo -n $ANTHROPIC_API_KEY | wc -c)"

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
