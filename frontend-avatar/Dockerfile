FROM node:18-alpine


LABEL maintainer="firstweek-team"
LABEL service="avatar-interface"
LABEL description="Avatar web interface with proxy to RAG API"

WORKDIR /app

COPY package*.json ./

RUN npm ci --omit=dev && \
    npm cache clean --force

COPY . .

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

USER nodejs

EXPOSE 3004

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD node -e "require('http').get('http://localhost:3004/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]

