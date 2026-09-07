
FROM node:18-alpine AS builder

LABEL maintainer="firstweek-team"
LABEL stage="builder"

WORKDIR /app
COPY package*.json ./

RUN npm ci

COPY . .
RUN npm run build


FROM node:18-alpine

LABEL maintainer="firstweek-team"
LABEL service="frontend"
LABEL description="React SPA served with Vite preview"

WORKDIR /app

COPY --from=builder /app/package*.json ./

RUN npm ci --include=dev && \
    npm cache clean --force

COPY --from=builder /app/src ./src
COPY --from=builder /app/public ./public
COPY --from=builder /app/index.html ./

COPY --from=builder /app/vite.config.js ./

COPY --from=builder /app/tailwind.config.js ./
COPY --from=builder /app/postcss.config.js ./

RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

USER nodejs

# Expose port
EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD node -e "require('http').get('http://127.0.0.1:5173', (r) => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

