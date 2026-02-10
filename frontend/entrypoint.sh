#!/bin/sh

# Extract hostname from REACT_APP_API_URL
# Removes protocol (http:// or https://) and trailing path/slashes
export BACKEND_HOST=$(echo "$REACT_APP_API_URL" | sed -e 's|^[^/]*//||' -e 's|/.*$||')

echo "Setting up Nginx..."
echo "API URL: $REACT_APP_API_URL"
echo "Backend Host: $BACKEND_HOST"

# Run envsubst to replace variables in template
# specific check for variables to avoid replacing $host or $remote_addr if they were in the template (though nginx docker handles this safely usually)
envsubst '${REACT_APP_API_URL} ${BACKEND_HOST}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Start Nginx
exec nginx -g "daemon off;"
