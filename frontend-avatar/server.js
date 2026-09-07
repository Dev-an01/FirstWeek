require('dotenv').config();
const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');
const httpProxy = require('http-proxy');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 3004;
const RAG_API_URL = process.env.RAG_API_URL || 'http://localhost:8000';

// Trust the single reverse-proxy hop (Caddy) so Express derives protocol/ip
// from X-Forwarded-* only from that trusted upstream, not from arbitrary clients.
app.set('trust proxy', 1);

// Derive the avatar-video WebSocket origin from the SAME env the client config uses
// (see /config.js below) so the CSP connect-src exactly matches what the browser opens.
const avatarWsProtocol = process.env.AVATAR_VIDEO_PROTOCOL || 'ws';
const avatarWsHost = process.env.AVATAR_VIDEO_HOST || 'localhost';
const avatarWsPort = process.env.AVATAR_VIDEO_PORT !== undefined ? process.env.AVATAR_VIDEO_PORT : '8085';
const avatarWsOrigin = avatarWsPort
  ? `${avatarWsProtocol}://${avatarWsHost}:${avatarWsPort}`
  : `${avatarWsProtocol}://${avatarWsHost}`;

// Security headers (CSP, X-Frame-Options, nosniff, etc.). CSP is scoped to exactly
// what the avatar interface loads: same-origin scripts + the socket.io CDN, and
// WebSocket/XHR to self (STT proxy) and the avatar-video host.
app.use(helmet({
  contentSecurityPolicy: {
    useDefaults: true,
    directives: {
      defaultSrc: ["'self'"],
      // socket.io is now self-hosted (public/js/socket.io.min.js), so no CDN origin is needed.
      scriptSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", 'data:'],
      mediaSrc: ["'self'", 'blob:'],
      connectSrc: ["'self'", avatarWsOrigin],
      objectSrc: ["'none'"],
      frameAncestors: ["'self'"],
      // Do NOT force upgrade-insecure-requests: the avatar host may legitimately
      // use ws:// in local/dev deployments and upgrading it would break the socket.
      upgradeInsecureRequests: null,
    },
  },
  // The socket.io CDN script is a normal cross-origin <script>; COEP would block it.
  crossOriginEmbedderPolicy: false,
}));

// ============================================================================
// Proxy Headers Middleware - Must be FIRST, before any other middleware
// Handles X-Forwarded-Proto and X-Forwarded-Host from Caddy
// ============================================================================
app.use((req, res, next) => {
  // Get the forwarded protocol (http/https)
  const forwardedProto = req.get('X-Forwarded-Proto') || req.protocol;
  const forwardedHost = req.get('X-Forwarded-Host') || req.get('host');

  // Override request protocol and host
  Object.defineProperty(req, 'protocol', {
    value: forwardedProto,
    writable: true,
    configurable: true
  });

  if (forwardedHost) {
    req.headers.host = forwardedHost;
  }

  console.log(`[Proxy] ${req.method} ${forwardedProto}://${forwardedHost}${req.url}`);
  next();
});

// Create raw http-proxy instance for WebSocket
const wsProxy = httpProxy.createProxyServer({
  target: RAG_API_URL,
  ws: true
});

// Create proxy middleware for STT WebSocket
const sttProxy = createProxyMiddleware({
  target: RAG_API_URL,
  changeOrigin: true,
  ws: true,
  logLevel: 'debug',
  onProxyReqWs: (proxyReq, req, socket) => {
    console.log('[Proxy] WebSocket proxying STT request to:', RAG_API_URL);
  },
  onProxyReq: (proxyReq, req, res) => {
    console.log('[Proxy] HTTP request to:', req.url);
  },
  onError: (err, req, res) => {
    console.error('[Proxy] STT proxy error:', err.message);
    console.error('[Proxy] Error stack:', err.stack);
  }
});

// Apply proxy middleware
app.use('/api/v1/stt', sttProxy);

// Proxy RAG API HTTP requests
app.use('/api/v1/langgraph', createProxyMiddleware({
  target: RAG_API_URL,
  changeOrigin: true,
  logLevel: 'info'
}));

// Serve static files from public directory
app.use(express.static(path.join(__dirname, 'public')));

// Root endpoint serves the avatar interface
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'avatar-interface',
    timestamp: new Date().toISOString()
  });
});

// Serve runtime configuration to frontend
app.get('/config.js', (req, res) => {
  const config = {
    AVATAR_VIDEO_HOST: process.env.AVATAR_VIDEO_HOST || 'localhost',
    AVATAR_VIDEO_PORT: process.env.AVATAR_VIDEO_PORT !== undefined ? process.env.AVATAR_VIDEO_PORT : '8085',
    AVATAR_VIDEO_PROTOCOL: process.env.AVATAR_VIDEO_PROTOCOL || 'ws',
    AVATAR_VIDEO_PATH: process.env.AVATAR_VIDEO_PATH !== undefined ? process.env.AVATAR_VIDEO_PATH : ''
  };

  // Prevent caching by Cloudflare and browsers
  res.set('Content-Type', 'application/javascript');
  res.set('Cache-Control', 'no-store, no-cache, must-revalidate, private');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  res.send(`window.ENV_CONFIG = ${JSON.stringify(config, null, 2)};`);
});

// Start server and handle WebSocket upgrades
const server = app.listen(PORT, () => {
  console.log('='.repeat(60));
  console.log('🎭 FirstWeek Interface');
  console.log('='.repeat(60));
  console.log(`✅ Server running on port ${PORT}`);
  console.log(`🌐 Interface URL: http://localhost:${PORT}`);
  console.log(`📍 Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`🔌 WebSocket proxy enabled for: /api/v1/stt → ${RAG_API_URL}`);
  console.log('='.repeat(60));
});

// Handle WebSocket upgrade for proxied requests - Use raw http-proxy
server.on('upgrade', (req, socket, head) => {
  console.log('[Server] WebSocket upgrade request:', req.url);

  if (req.url.startsWith('/api/v1/stt')) {
    console.log('[Server] Proxying WebSocket upgrade to:', RAG_API_URL + req.url);

    // Use raw http-proxy for WebSocket - more reliable than middleware
    wsProxy.ws(req, socket, head, (err) => {
      if (err) {
        console.error('[Server] WebSocket proxy error:', err.message);
        socket.destroy();
      }
    });
  } else {
    console.log('[Server] No proxy handler for WebSocket path:', req.url);
    socket.destroy();
  }
});
