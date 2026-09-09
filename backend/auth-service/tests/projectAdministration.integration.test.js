// Opt in against the isolated demo only: FIRSTWEEK_TEST_DATABASE=1 node --test <this file>
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

test('real PostgreSQL membership authority, concurrency, validation and empty projects',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    process.env.NODE_ENV = 'test';
    const { prisma } = require('../shared/lib/prisma');
    assert.equal((await prisma.$queryRaw`SELECT current_database() AS name`)[0].name, 'firstweek_demo');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const id = `m1-test-${randomUUID()}`;
    const companyIds = [id, `${id}-other`];
    let server;
    try {
      for (const companyId of companyIds) await prisma.company.create({ data: { id: companyId, name: 'M1 verification', allowedDomains: [] } });
      const people = {};
      for (const [name, overrides] of Object.entries({ admin: { role: 'COMPANY_ADMIN' }, admin2: { role: 'COMPANY_ADMIN' },
        member: {}, second: {}, outsider: { companyId: companyIds[1] }, unverified: { isCompanyVerified: false },
        inactive: { isActive: false }, email: { emailVerified: false } })) {
        people[name] = await prisma.user.create({ data: { username: `${id}-${name}`, firstName: name, lastName: 'Test',
          password: 'not-a-login-hash', companyId: id, isActive: true, isCompanyVerified: true, emailVerified: true, ...overrides } });
      }
      const actor = people.admin;
      await assert.rejects(createProject(prisma, people.member, { name: 'Denied' }), { status: 403 });
      await assert.rejects(createProject(prisma, actor, { name: 'Scope injection', companyId: companyIds[1] }), { status: 400 });
      const project = await createProject(prisma, actor, { name: 'Administration test', description: 'Private test project' });
      assert.equal(project.companyId, id); assert.equal(project.hasCuratedKnowledge, false);
      const change = (user, action, body, target) => manageProject(prisma, user, project.id, action, body, target);
      for (const name of ['outsider','unverified','inactive','email']) {
        await assert.rejects(change(actor, 'add', { username: people[name].username, role: 'MEMBER' }), { status: 404 });
      }
      await assert.rejects(change(actor, 'add', { username: people.member.username, role: 'ADMIN' }), { status: 400 });
      await change(actor, 'add', { username: people.member.username, role: 'MEMBER' });
      await assert.rejects(change(people.member, 'role', { role: 'MAINTAINER' }, people.member.id), { status: 403 });
      await assert.rejects(change(people.admin2, 'settings', { name: 'Not a member' }), { status: 404 });
      await assert.rejects(change(actor, 'remove', {}, actor.id), { status: 409 });
      await change(actor, 'add', { username: people.second.username, role: 'MAINTAINER' });
      const demotions = await Promise.allSettled([
        change(actor, 'role', { role: 'MEMBER' }, actor.id),
        change(people.second, 'role', { role: 'MEMBER' }, people.second.id),
      ]);
      assert.equal(demotions.filter(x => x.status === 'fulfilled').length, 1);
      assert.equal(demotions.find(x => x.status === 'rejected').reason.status, 409);
      const scope = { companyId: id, projectId: project.id };
      let maintainer = await prisma.projectMember.findFirst({ where: { ...scope, role: 'MAINTAINER' } });
      const maintainerUser = Object.values(people).find(user => user.id === maintainer.userId);
      await change(maintainerUser, 'role', { role: 'MAINTAINER' }, actor.id);
      await change(maintainerUser, 'role', { role: 'MAINTAINER' }, people.second.id);
      const removals = await Promise.allSettled([
        change(actor, 'remove', {}, people.second.id),
        change(people.second, 'remove', {}, actor.id),
      ]);
      assert.equal(removals.filter(x => x.status === 'fulfilled').length, 1);
      assert.equal(removals.find(x => x.status === 'rejected').reason.status, 404);
      assert.equal(await prisma.projectMember.count({ where: { ...scope, role: 'MAINTAINER' } }), 1);
      maintainer = await prisma.projectMember.findFirst({ where: { ...scope, role: 'MAINTAINER' } });

      // Use the real router/database; replace only session parsing with explicit test identities.
      const Module = require('node:module');
      const original = Module._load;
      Module._load = function(request, parent, ...args) {
        if (parent?.filename.endsWith('/routes/firstweekRoutes.js') && request === '../middleware/authMiddleware') {
          return { requireAuth: async (req, res, next) => {
            req.user = Object.values(people).find(user => user.id === req.get('x-test-user'));
            return req.user ? next() : res.status(401).end();
          } };
        }
        return original.call(this, request, parent, ...args);
      };
      let router;
      try { router = require('../routes/firstweekRoutes'); } finally { Module._load = original; }
      const express = require('express'); const app = express(); app.use(express.json()); app.use('/api/firstweek', router);
      server = await new Promise(resolve => { const listener = app.listen(0, '127.0.0.1', () => resolve(listener)); });
      const origin = `http://127.0.0.1:${server.address().port}`;
      const base = `${origin}/api/firstweek/projects/${project.id}`;
      const headers = { 'x-test-user': maintainer.userId, origin, 'content-type': 'application/json' };
      const empty = await fetch(base, { headers }); assert.equal(empty.status, 200);
      const body = await empty.json(); assert.equal(body.knowledgeStatus, 'empty'); assert.deepEqual(body.documents, []);
      assert.equal((await fetch(base)).status, 401);
      for (const user of [people.admin2, people.outsider]) assert.equal((await fetch(base, { headers: { ...headers, 'x-test-user': user.id } })).status, 404);
      for (const invalid of [{ ...headers, origin: 'https://attacker.invalid' }, { ...headers, origin: 'null' },
        { ...headers, 'sec-fetch-site': 'cross-site' }, { 'x-test-user': maintainer.userId, 'content-type': 'application/json' }]) {
        assert.equal((await fetch(base, { method: 'PATCH', headers: invalid, body: '{"name":"Denied"}' })).status, 403);
      }
      assert.equal((await fetch(base, { method: 'PATCH', headers: { ...headers, 'content-type': 'text/plain' }, body: '{}' })).status, 415);
      for (const invalid of [[], null, { name: '' }, { name: 'x'.repeat(121) }, { name: 'Valid', companyId: 'spoof' }]) {
        assert.equal((await fetch(base, { method: 'PATCH', headers, body: JSON.stringify(invalid) })).status, 400);
      }
      assert.equal((await fetch(base, { method: 'PATCH', headers, body: '{"name":"Changed","description":"Maintained context"}' })).status, 200);
      assert.equal((await (await fetch(base, { headers })).json()).name, 'Changed');
      const answer = await fetch(`${base}/ask`, { method: 'POST', headers, body: '{"question":"What is this project?"}' });
      assert.equal((await answer.json()).mode, 'no-evidence');
      console.log('Verified two concurrent demotions and reciprocal removals leave one maintainer; HTTP scope, role, JSON, origin and empty-state checks pass.');
    } finally {
      if (server) await new Promise(resolve => server.close(resolve));
      await prisma.project.deleteMany({ where: { companyId: { in: companyIds } } });
      await prisma.user.deleteMany({ where: { companyId: { in: companyIds } } });
      await prisma.company.deleteMany({ where: { id: { in: companyIds } } });
      await prisma.$disconnect();
    }
  });
