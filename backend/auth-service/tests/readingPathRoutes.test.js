const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const express = require('express');

let call;
let server;
let base;
const prisma = { projectMember: { findFirst: async ({ where }) => where.userId === 'reader' && where.companyId === 'company-a' && where.projectId === 'alpha'
  ? { role: 'MAINTAINER', project: { id: 'alpha', companyId: 'company-a', isActive: true } } : null } };
const readingPaths = {
  readPath: async (_prisma, actor, projectId) => { call = { actor, projectId }; return { canManage: true, steps: [], managedSteps: [], completed: 0, total: 0 }; },
  saveStep: async (_prisma, actor, projectId, body, id) => { call = { actor, projectId, body, id }; return { id: id || 'r-created' }; },
  removeStep: async (_prisma, actor, projectId, id) => { call = { actor, projectId, id }; return { id }; },
  reorderSteps: async (_prisma, actor, projectId, body) => { call = { actor, projectId, body }; return body; },
  completeStep: async (_prisma, actor, projectId, id, body) => { call = { actor, projectId, id, body }; return { id, completed: true }; },
};
const originalLoad = Module._load;
Module._load = function load(request, parent, ...args) {
  if (parent?.filename.endsWith('/routes/firstweekRoutes.js')) {
    if (request === '../shared/lib/prisma') return { prisma };
    if (request === '../services/readingPaths') return readingPaths;
    if (request === '../middleware/authMiddleware') return { requireAuth: (req, res, next) => {
      if (!req.headers['x-test-user']) return res.status(401).end();
      req.user = { id: req.headers['x-test-user'], companyId: 'company-a', isActive: true, isCompanyVerified: true };
      return next();
    } };
  }
  return originalLoad.call(this, request, parent, ...args);
};
const routes = require('../routes/firstweekRoutes');
Module._load = originalLoad;

before(async () => {
  const app = express();
  app.use(express.json());
  app.use('/api/firstweek', routes);
  server = await new Promise(resolve => { const listener = app.listen(0, '127.0.0.1', () => resolve(listener)); });
  base = `http://127.0.0.1:${server.address().port}/api/firstweek`;
});
after(async () => { if (server) await new Promise(resolve => server.close(resolve)); });

test('reading-path reads are authenticated, project scoped, and private-cache disabled', async () => {
  const path = `${base}/projects/alpha/reading-path`;
  assert.equal((await fetch(path)).status, 401);
  assert.equal((await fetch(path, { headers: { 'X-Test-User': 'outsider' } })).status, 404);
  const response = await fetch(path, { headers: { 'X-Test-User': 'reader' } });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(call.actor.id, 'reader');
  assert.equal(call.actor.companyId, 'company-a');
  assert.equal(call.projectId, 'alpha');
});

test('reading-path writes require exact-origin JSON and derive scope from the session and URL', async () => {
  const path = `${base}/projects/alpha/reading-path`;
  const body = { title: 'Read this', description: '', documentId: 'm-source', focus: null, experience: null,
    companyId: 'company-b', projectId: 'beta', userId: 'outsider' };
  assert.equal((await fetch(path, { method: 'POST', headers: { 'X-Test-User': 'reader', 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).status, 403);
  assert.equal((await fetch(path, { method: 'POST', headers: { 'X-Test-User': 'reader', Origin: new URL(base).origin, 'Content-Type': 'text/plain' }, body: '{}' })).status, 415);
  const response = await fetch(path, { method: 'POST', headers: { 'X-Test-User': 'reader', Origin: new URL(base).origin, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  assert.equal(response.status, 201);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(call.actor.id, 'reader');
  assert.equal(call.actor.companyId, 'company-a');
  assert.equal(call.projectId, 'alpha');
  assert.equal(call.body.companyId, 'company-b');
});

test('completion identity and reorder project scope cannot be chosen by the request body', async () => {
  const headers = { 'X-Test-User': 'reader', Origin: new URL(base).origin, 'Content-Type': 'application/json' };
  const completion = await fetch(`${base}/projects/alpha/reading-path/r-one/completion`, { method: 'PUT', headers,
    body: JSON.stringify({ revision: 2, userId: 'outsider', companyId: 'company-b', projectId: 'beta' }) });
  assert.equal(completion.status, 200);
  assert.equal(call.actor.id, 'reader');
  assert.equal(call.projectId, 'alpha');
  assert.equal(call.id, 'r-one');
  const order = await fetch(`${base}/projects/alpha/reading-path/order`, { method: 'PUT', headers,
    body: JSON.stringify({ stepIds: ['r-one'], projectId: 'beta' }) });
  assert.equal(order.status, 200);
  assert.equal(call.actor.companyId, 'company-a');
  assert.equal(call.projectId, 'alpha');
});
