# Frontend Dockerfile for Chatbot System

FROM node:18-alpine AS builder

# Accept build arguments from Railway
ARG VITE_API_BASE_URL
ARG VITE_WS_URL
ARG VITE_API_PREFIX
ARG VITE_APP_NAME
ARG VITE_ENVIRONMENT

# Make them available as environment variables during build
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_API_PREFIX=$VITE_API_PREFIX
ENV VITE_APP_NAME=$VITE_APP_NAME
ENV VITE_ENVIRONMENT=$VITE_ENVIRONMENT

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application code (excluding .env via .dockerignore)
COPY . .

# Debug: List env vars during build to verify Railway variables are present
RUN echo "Build-time VITE_WS_URL: ${VITE_WS_URL}"

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Install gettext for envsubst
RUN apk add --no-cache gettext

# Copy built files to nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration template and startup script
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose port (Railway uses $PORT)
EXPOSE 80

# Start nginx using startup script
CMD ["/start.sh"]
