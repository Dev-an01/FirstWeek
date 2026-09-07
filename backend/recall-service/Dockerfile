
# Step 1: Choose the base image
FROM node:18-alpine

# Step 2: Set metadata (optional but good practice)
# This helps identify the image and its purpose
LABEL maintainer="firstweek-team"
LABEL service="recall-service"
LABEL description="Recall.ai bot management service"

# Step 3: Set working directory
WORKDIR /app

# Step 4: Copy dependency files FIRST, uses cached version if unchanged.
COPY package*.json ./

# Step 5: Install production dependencies
# npm ci = "clean install" - faster and more reliable than npm install , --omit=dev for avoiding the dev dependencies
RUN npm ci --omit=dev && \
    npm cache clean --force

# Step 6: Copy application code
COPY . .

# Step 7: Create non-root user for security
# Running as root inside containers is a security risk
# If someone exploits your app, they have root access to the container
# Alpine uses 'addgroup' and 'adduser' (not 'groupadd' and 'useradd')
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

# Step 8: Switch to non-root user
# All subsequent commands and the app itself run as this user
USER nodejs

# Step 9: Expose the port(just for documentation, actual mapping is done in docker-compose)
EXPOSE 3003

# Step 10: Health check (critical for production!)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD node -e "require('http').get('http://localhost:3003/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

# Step 11: Default command to run the application
# using exec form to avoid shell interpretation and signal issues
CMD ["node", "src/server.js"]
