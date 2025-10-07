#!/bin/sh

# Use Railway's PORT or default to 8080
PORT=${PORT:-8080}
export PORT

# Replace PORT in nginx config
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Debug: show what port we're using
echo "Starting nginx on port: $PORT"
cat /etc/nginx/conf.d/default.conf | head -5

# Start nginx
nginx -g 'daemon off;'
