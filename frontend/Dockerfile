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

# Copy custom entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 10000

# Use custom entrypoint to handle advanced variable substitution
ENTRYPOINT ["/entrypoint.sh"]
