
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
LABEL service="auth-service"
LABEL description="Authentication service with Prisma ORM"

WORKDIR /app

COPY --from=builder /app/package*.json ./

COPY --from=builder /app/node_modules ./node_modules

COPY . .

# Copy generated Prisma client from builder (must come after COPY . . to not be overwritten)
COPY --from=builder /app/shared/lib/generated ./shared/lib/generated

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

USER nodejs

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=120s \
    CMD node -e "require('http').get('http://localhost:3001/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
CMD ["node", "server.js"]
