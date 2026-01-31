# Stage 1: Build
FROM node:18-alpine as build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
# Use --legacy-peer-deps if needed, or just ci
RUN npm install

# Copy source
COPY . ./

# Build
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Install gettext for envsubst
RUN apk add --no-cache gettext

# Copy build artifacts
COPY --from=build /app/build /usr/share/nginx/html

# Copy manifest/template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 10000

# Environment variables to substitute (explicitly listing them is not strictly needed if we use output redirection, 
# but Nginx 1.19+ has built-in templating support!)
# Nginx Docker image automatically runs envsubst on /etc/nginx/templates/*.template 
# and outputs to /etc/nginx/conf.d/*.conf if NGINX_ENVSUBST_OUTPUT_DIR is default.
# We just need to ensure the variables are passed.

CMD ["nginx", "-g", "daemon off;"]
