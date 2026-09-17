const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const teams = require('../services/companyTeams');

test('company teams preserve tenant/project isolation, authority, assignments and bounded concurrency',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const companyId = `teams-${randomUUID()}`, otherId = `${companyId}-other`;
    let server;
    const people = {};
    try {
      assert.equal((await prisma.$queryRaw`SELECT current_database() AS name`)[0].name, 'firstweek_demo');
      for (const id of [companyId, otherId]) await prisma.company.create({ data: { id, name: 'Team tests', allowedDomains: [] } });
      for (const [name, extra] of Object.entries({ admin: { role: 'COMPANY_ADMIN' }, member: {},
        foreign: { role: 'COMPANY_ADMIN', companyId: otherId }, inactive: { isActive: false },
        unverified: { isCompanyVerified: false }, noEmail: { emailVerified: false } })) {
        people[name] = await prisma.user.create({ data: { username: `${companyId}-${name}`, firstName: name, lastName: 'Test',
          companyId, password: 'not-a-login-hash', isActive: true, isCompanyVerified: true, emailVerified: true, ...extra } });
      }
      const { admin, member, foreign } = people;
      const body = { name: 'Engineering', description: 'Maintained company team' };
      await assert.rejects(teams.saveTeam(prisma, { ...member, role: 'COMPANY_ADMIN' }, body), { status: 403 });
      const team = await teams.saveTeam(prisma, admin, body);
      const target = { username: member.username, assignment: 'Maintain development tools' };
      for (const actor of [member, people.inactive, people.unverified]) {
        for (const operation of [() => teams.saveTeam(prisma, actor, body, team.id),
          () => teams.deleteTeam(prisma, actor, team.id, {}), () => teams.assignMember(prisma, actor, team.id, target)]) {
          await assert.rejects(operation(), { status: 403 });
        }
      }
      for (const operation of [() => teams.saveTeam(prisma, foreign, body, team.id),
        () => teams.deleteTeam(prisma, foreign, team.id, {}), () => teams.assignMember(prisma, foreign, team.id, target)]) {
        await assert.rejects(operation(), { status: 404 });
      }
      for (const invalid of [null, [], {}, { ...body, companyId: otherId }, { ...body, name: ' ' },
        { ...body, description: '\u0000' }, { ...body, name: '\ud800' }, { ...body, name: 'x'.repeat(121) }]) {
        await assert.rejects(teams.saveTeam(prisma, admin, invalid), { status: 400 });
      }
      await assert.rejects(teams.saveTeam(prisma, admin, { ...body, name: 'ENGINEERING' }), { status: 409 });
      for (const name of ['foreign', 'inactive', 'unverified', 'noEmail']) {
        await assert.rejects(teams.assignMember(prisma, admin, team.id, { ...target, username: people[name].username }), { status: 404 });
      }
      await assert.rejects(teams.assignMember(prisma, admin, team.id, { ...target, userId: foreign.id }), { status: 400 });
      await teams.assignMember(prisma, admin, team.id, target);
      await teams.assignMember(prisma, admin, team.id, { ...target, assignment: 'Explicit assignment updated' });
      const directory = await teams.listTeams(prisma, member);
      assert.equal(directory.canManage, false);
      assert.equal(directory.teams[0].assignments.length, 1);
      assert.equal(directory.teams[0].assignments[0].assignment, 'Explicit assignment updated');
      assert.deepEqual(Object.keys(directory.teams[0].assignments[0].user).sort(), ['firstName', 'lastName', 'username']);
      assert.deepEqual((await teams.listTeams(prisma, foreign)).teams, []);
      assert.equal(await prisma.projectMember.count({ where: { companyId } }), 0);
      await assert.rejects(teams.listTeams(prisma, { ...admin, companyId: otherId }), { status: 403 });
      await prisma.user.update({ where: { id: admin.id }, data: { role: 'EMPLOYEE' } });
      await assert.rejects(teams.saveTeam(prisma, admin, body, team.id), { status: 403 });
      await prisma.user.update({ where: { id: admin.id }, data: { role: 'COMPANY_ADMIN' } });
      await prisma.company.update({ where: { id: companyId }, data: { isActive: false } });
      await assert.rejects(teams.listTeams(prisma, member), { status: 403 });
      await assert.rejects(teams.saveTeam(prisma, admin, body, team.id), { status: 403 });
      await prisma.company.update({ where: { id: companyId }, data: { isActive: true } });
      await prisma.user.update({ where: { id: member.id }, data: { isActive: false } });
      assert.deepEqual((await teams.listTeams(prisma, admin)).teams[0].assignments, []);
      await assert.rejects(teams.listTeams(prisma, member), { status: 403 });
      await teams.assignMember(prisma, admin, team.id, { username: member.username }, true);
      await prisma.user.update({ where: { id: member.id }, data: { isActive: true } });
      await teams.assignMember(prisma, admin, team.id, target);
      // Even an identically named target team cannot silently transfer the assignment to another company.
      await prisma.companyTeam.create({ data: { companyId: otherId, id: team.id, name: 'Other team' } });
      await assert.rejects(prisma.user.update({ where: { id: member.id }, data: { companyId: otherId } }), { code: 'P2003' });
      await assert.rejects(prisma.teamAssignment.create({ data: { companyId, teamId: team.id, userId: foreign.id, assignment: 'Foreign' } }), { code: 'P2003' });
      await teams.saveTeam(prisma, admin, { name: 'Platform', description: 'Renamed team' }, team.id);
      await prisma.$disconnect();
      assert.equal((await teams.listTeams(prisma, member)).teams[0].name, 'Platform');

      // Use the actual router and database, substituting only session identity.
      const Module = require('node:module'), original = Module._load;
      Module._load = function(request, parent, ...args) {
        if (parent?.filename.endsWith('/routes/firstweekRoutes.js') && request === '../middleware/authMiddleware') {
          return { requireAuth: (req, res, next) => {
            req.user = Object.values(people).find(user => user.id === req.get('x-test-user'));
            return req.user ? next() : res.status(401).end();
          } };
        }
        return original.call(this, request, parent, ...args);
      };
      let router;
      try { router = require('../routes/firstweekRoutes'); } finally { Module._load = original; }
      const express = require('express'), app = express();
      app.use(express.json()); app.use('/api/firstweek', router);
      server = await new Promise(resolve => { const s = app.listen(0, '127.0.0.1', () => resolve(s)); });
      const origin = `http://127.0.0.1:${server.address().port}`, base = `${origin}/api/firstweek/company/teams`;
      const headers = { 'x-test-user': admin.id, origin, 'content-type': 'application/json' };
      const send = (method, suffix, data, extra = {}) => fetch(base + suffix, { method, headers: { ...headers, ...extra }, body: JSON.stringify(data) });
      assert.equal((await fetch(base)).status, 401);
      const read = await fetch(base, { headers: { ...headers, 'x-test-user': member.id } });
      assert.equal(read.status, 200); assert.equal(read.headers.get('cache-control'), 'no-store');
      assert.equal((await send('POST', '', body, { origin: 'https://attacker.invalid' })).status, 403);
      assert.equal((await send('POST', '', body, { 'content-type': 'text/plain' })).status, 415);
      assert.equal((await send('POST', '', body, { 'x-test-user': member.id })).status, 403);
      assert.equal((await send('POST', '', { ...body, companyId: otherId })).status, 400);
      assert.equal((await send('PATCH', '/missing', body)).status, 404);
      const added = await send('POST', '', body); assert.equal(added.status, 201);
      const addedId = (await added.json()).id;
      assert.equal((await send('PUT', `/${addedId}/assignments`, target)).status, 200);
      assert.equal((await send('DELETE', `/${addedId}/assignments`, { username: member.username })).status, 200);
      assert.equal((await send('DELETE', `/${addedId}`, {})).status, 200);

      const { companyContext, companySources } = require('../services/companyContext');
      let context = await companyContext(prisma, member);
      assert.ok(companySources(context, 'Platform assignment').some(s => s.content.includes(target.assignment)));
      assert.deepEqual(companySources(context, 'zzzzunfindable'), []);
      const beforeRename = context.hash;
      await prisma.user.update({ where: { id: member.id }, data: { firstName: 'Renamed' } });
      context = await companyContext(prisma, admin);
      assert.notEqual(context.hash, beforeRename);
      assert.ok(companySources(context, 'Renamed').some(s => s.content.includes('Renamed')));
      const { createProject, manageProject } = require('../services/projectAdministration');
      const store = require('../services/projectConversations');
      const projects = await Promise.all(['One', 'Two'].map(name => createProject(prisma, admin, { name })));
      const pending = [];
      for (const p of projects) {
        await manageProject(prisma, admin, p.id, 'add', { username: member.username, role: 'MEMBER' });
        const version = (await prisma.project.findUnique({ where: { companyId_id: { companyId, id: p.id } } })).knowledgeVersion;
        for (const actor of [admin, member]) {
          const snapshot = { hash: context.hash, version };
          const c = await store.createConversation(prisma, actor, p.id, snapshot);
          const row = (await store.beginTurn(prisma, actor, p.id, c.id, snapshot, { question: 'Shared company assignment', requestId: randomUUID() })).conversation;
          pending.push({ p, actor, row, snapshot });
        }
      }
      await teams.assignMember(prisma, admin, team.id, { ...target, assignment: 'Updated during generation' });
      for (const { p, actor, row, snapshot } of pending) {
        await assert.rejects(store.finishTurn(prisma, actor, p.id, row, snapshot, { answer: 'Stale', sources: [] }), { status: 409 });
      }
      assert.ok((await prisma.projectConversation.findMany({ where: { companyId } })).every(c => !c.pendingId && !c.pendingQuestion && c.turns.length === 0));
      await prisma.project.deleteMany({ where: { companyId } });

      await prisma.companyTeam.createMany({ data: Array.from({ length: 98 }, (_, i) => ({ companyId, id: `quota-${i}`, name: `Quota ${i}` })) });
      const concurrent = await Promise.allSettled(['Last slot A', 'Last slot B'].map(name => teams.saveTeam(prisma, admin, { name, description: '' })));
      assert.equal(concurrent.filter(r => r.status === 'fulfilled').length, 1);
      assert.equal(concurrent.find(r => r.status === 'rejected').reason.status, 409);
      const bulk = Array.from({ length: 200 }, (_, i) => ({ id: `quota-user-${randomUUID()}`, username: `${companyId}-quota-${i}`,
        companyId, firstName: 'Quota', lastName: 'Test', password: 'not-a-login-hash', isActive: true, isCompanyVerified: true, emailVerified: true }));
      await prisma.user.createMany({ data: bulk });
      await prisma.teamAssignment.createMany({ data: bulk.slice(0, 198).map(u => ({ companyId, teamId: team.id, userId: u.id, assignment: 'Quota fixture' })) });
      const slots = await Promise.allSettled(bulk.slice(198).map(u => teams.assignMember(prisma, admin, team.id, { username: u.username, assignment: 'Last assignment' })));
      assert.equal(slots.filter(r => r.status === 'fulfilled').length, 1);
      assert.equal(slots.find(r => r.status === 'rejected').reason.status, 409);
      await teams.assignMember(prisma, admin, team.id, { ...target, assignment: 'Still editable at capacity' });
      assert.equal(await prisma.teamAssignment.count({ where: { companyId, teamId: team.id } }), 200);
      await prisma.user.delete({ where: { id: member.id } });
      assert.equal(await prisma.teamAssignment.count({ where: { companyId, userId: member.id } }), 0);
      await teams.deleteTeam(prisma, admin, team.id, {});
      assert.equal(await prisma.teamAssignment.count({ where: { companyId, teamId: team.id } }), 0);
    } finally {
      if (server) await new Promise(resolve => server.close(resolve));
      await prisma.project.deleteMany({ where: { companyId: { in: [companyId, otherId] } } });
      await prisma.companyTeam.deleteMany({ where: { companyId: { in: [companyId, otherId] } } });
      await prisma.user.deleteMany({ where: { companyId: { in: [companyId, otherId] } } });
      await prisma.company.deleteMany({ where: { id: { in: [companyId, otherId] } } });
      await prisma.$disconnect();
    }
  });
