FROM node:18-alpine AS builder

RUN apk add --no-cache openssl

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run generate

RUN npm prune --production

FROM node:18-alpine

RUN apk add --no-cache openssl

LABEL maintainer="firstweek-team"
LABEL service="chat-service"
LABEL description="Chat service with Prisma ORM and Socket.io"

WORKDIR /app
COPY --from=builder /app/package*.json ./

COPY --from=builder /app/node_modules ./node_modules

# Copy generated Prisma clients from builder stage
COPY --from=builder /app/shared/lib/generated ./shared/lib/generated

COPY . .

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

USER nodejs

EXPOSE 3002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD node -e "require('http').get('http://localhost:3002/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

# Start the application
CMD ["node", "server.js"]

