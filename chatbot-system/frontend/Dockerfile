# Frontend Dockerfile for Chatbot System

FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

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
