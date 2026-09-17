// Loopback-only development host. Reuses the real auth and FirstWeek routers.
// Requires the isolated firstweek_demo database described in the runbook.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const localRequire = createRequire(path.join(__dirname, '../backend/auth-service/package.json'));
const root = path.resolve(__dirname, '..');
const local = path.join(root, '.firstweek/local');
fs.mkdirSync(local, { recursive: true, mode: 0o700 });
const configPath = path.join(local, 'runtime.json');
if (!fs.existsSync(configPath)) fs.writeFileSync(configPath, JSON.stringify({
  serviceToken: crypto.randomBytes(32).toString('hex'),
  accessSecret: crypto.randomBytes(32).toString('hex'),
  refreshSecret: crypto.randomBytes(32).toString('hex'),
}), { mode: 0o600 });
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
Object.assign(process.env, {
  DATABASE_URL: process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo',
  JWT_ACCESS_SECRET: config.accessSecret, JWT_REFRESH_SECRET: config.refreshSecret,
  FIRSTWEEK_SERVICE_TOKEN: config.serviceToken, FIRSTWEEK_RAG_URL: 'http://127.0.0.1:8003',
  FIRSTWEEK_ORIGIN: process.env.FIRSTWEEK_ORIGIN || 'http://127.0.0.1:5173',
  NODE_ENV: 'development', LOG_LEVEL: 'warn', COOKIE_DOMAIN: '',
  GMAIL_ADDRESS: '', GMAIL_PASSWORD: '', ONBOARDING_SERVICE_URL: 'http://127.0.0.1:8002',
});
const express = localRequire('express');
const cookieParser = localRequire('cookie-parser');
const bcrypt = localRequire('bcryptjs');
const { prisma } = require('../backend/auth-service/shared/lib/prisma');
async function main() {
  const credentialsPath = path.join(local, 'access.json');
  let credentials;
  if (fs.existsSync(credentialsPath)) credentials = JSON.parse(fs.readFileSync(credentialsPath, 'utf8'));
  else {
    credentials = { username: 'firstweek_demo', password: crypto.randomBytes(18).toString('base64url') + '!aA1' };
    fs.writeFileSync(credentialsPath, JSON.stringify(credentials, null, 2), { mode: 0o600 });
  }
  await prisma.company.upsert({ where: { id: 'local-workspace' }, create: { id: 'local-workspace', name: 'Local project workspace', allowedDomains: [] }, update: {} });
  const user = await prisma.user.upsert({ where: { username: credentials.username }, create: {
    username: credentials.username, firstName: 'Local', lastName: 'Member', password: await bcrypt.hash(credentials.password, 12),
    role: 'COMPANY_ADMIN', companyId: 'local-workspace', isCompanyVerified: true, emailVerified: true,
  }, update: {} });
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'knowledge/firstweek/manifest.json'), 'utf8'));
  await prisma.project.updateMany({ where: { companyId: 'local-workspace', id: { in: manifest.retiredProjectIds || [] } }, data: { isActive: false } });
  for (const project of manifest.projects) {
    await prisma.project.upsert({ where: { companyId_id: { companyId: 'local-workspace', id: project.id } },
      create: { companyId: 'local-workspace', id: project.id, name: project.name, description: project.summary,
        members: { create: { userId: user.id, role: 'MAINTAINER' } } },
      update: {} });
  }
  const app = express();
  app.use(express.json({ limit: '2mb' }));
  app.use(cookieParser());
  // This local host exposes only login/session and FirstWeek routes, not mail or avatar integrations.
  const controller = require('../backend/auth-service/controllers/userController');
  const auth = require('../backend/auth-service/middleware/authMiddleware');
  app.post('/api/users/login', controller.loginUser);
  app.get('/api/users/me', auth.requireAuth, controller.getCurrentUserProfile);
  app.post('/api/users/logout', auth.requireAuth, controller.logoutUser);
  app.post('/api/users/refresh', auth.validateRefreshToken, controller.refreshToken);
  app.use('/api/firstweek', require('../backend/auth-service/routes/firstweekRoutes'));
  app.use((error, req, res, next) => {
    const details = { name: error?.name, type: error?.type, status: error?.status, code: error?.code };
    console.error('Local workspace request failed:', details);
    const status = Number.isInteger(error?.status) && error.status >= 400 && error.status < 500 ? error.status : 500;
    res.status(status).json({ error: status === 413 ? 'Request is too large.' : status === 400 ? 'Request body is invalid.' : 'Local workspace request failed.' });
  });
  const server = app.listen(3003, '127.0.0.1', () => console.log('FirstWeek local auth: http://127.0.0.1:3003. Local-only credentials: .firstweek/local/access.json'));
  process.on('SIGTERM', () => server.close(() => prisma.$disconnect().then(() => process.exit(0))));
  process.on('SIGINT', () => server.close(() => prisma.$disconnect().then(() => process.exit(0))));
}
main().catch(() => { console.error('Local workspace failed to start. Check the isolated database setup in the runbook.'); process.exitCode = 1; prisma.$disconnect(); });
