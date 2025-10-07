#!/bin/sh

# Use Railway's PORT or default to 80
export NGINX_PORT=${PORT:-80}

# Replace PORT in nginx config
envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Start nginx
nginx -g 'daemon off;'
