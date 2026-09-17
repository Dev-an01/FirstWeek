import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { createPublicHandler } from './server/publicHandler.js';

function mountPublicApi(server) {
  // Server-only values from the usual local Vite env files. Nothing here is
  // returned to the browser; only VITE_* settings belong in client code.
  const localEnv = loadEnv(server.config.mode, server.config.envDir,
    ['FIRSTWEEK_PUBLIC_', 'OPENAI_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY', 'UPSTASH_REDIS_REST_']);
  const publicHandler = createPublicHandler({ env: { ...localEnv, ...process.env } });
  server.middlewares.use((req, res, next) => {
    if (req.url?.split('?')[0] !== '/api/public') return next();
    return publicHandler(req, res).catch(() => { res.statusCode = 500; res.end('{"error":"Public demo unavailable."}'); });
  });
}

export default defineConfig({
  plugins: [react(), {
    name: 'firstweek-public-api',
    configureServer: mountPublicApi,
    configurePreviewServer: mountPublicApi,
  }],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0', // Required for Docker
    allowedHosts: [
      'example.invalid',
      'example.invalid',
      'example.invalid',
      'localhost',
      '.ngrok-free.dev',
    ],
    proxy: {
      // Onboarding service proxy - must come before general /api proxy
      '/api/onboarding': {
        target: process.env.ONBOARDING_SERVICE_URL || 'http://onboarding-service:8002',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api\/onboarding/, '/api/v1'),
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.headers.cookie) {
              proxyReq.setHeader('cookie', req.headers.cookie);
            }
          });
        },
      },
      // RAG API proxy - must come before general /api proxy
      '/api/rag': {
        target: process.env.RAG_SERVICE_URL || 'http://ai-officer-api:8000',
        changeOrigin: true,
        secure: false,
        followRedirects: false,
        rewrite: (path) => path.replace(/^\/api\/rag/, '/api/v1'),
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.headers.cookie) {
              proxyReq.setHeader('cookie', req.headers.cookie);
            }
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            // Rewrite Location header to hide internal Docker hostname
            if (proxyRes.headers.location) {
              const location = proxyRes.headers.location;
              // Replace internal hostname with relative path
              proxyRes.headers.location = location
                .replace('http://rag-api:8000/api/v1', '/api/rag')
                .replace('http://ai-officer-api:8000/api/v1', '/api/rag')
                .replace('http://localhost:8000/api/v1', '/api/rag');
            }
          });
        },
      },
      // Chat service proxy - must come before general /api proxy
      '/api/chat': {
        target: process.env.CHAT_SERVICE_URL || 'http://localhost:3002',
        changeOrigin: true,
        secure: false,
        // Forward cookies from browser to backend
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // Forward all cookies
            if (req.headers.cookie) {
              proxyReq.setHeader('cookie', req.headers.cookie);
            }
          });
        },
      },
      // Auth service proxy (for all other /api calls)
      '/api': {
        target: process.env.AUTH_SERVICE_URL || 'http://localhost:3001',
        changeOrigin: true,
        secure: false,
        // Forward cookies from browser to backend
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // Forward all cookies
            if (req.headers.cookie) {
              proxyReq.setHeader('cookie', req.headers.cookie);
            }
          });
        },
      },
    },
  },
});
