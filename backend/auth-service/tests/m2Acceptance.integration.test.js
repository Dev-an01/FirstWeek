const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const express = require('express');

test('M2 profiles, reading progress and maintained company evidence stay fresh and private together',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const documents = require('../services/projectDocuments');
    const profiles = require('../services/onboardingProfiles');
    const paths = require('../services/readingPaths');
    const teams = require('../services/companyTeams');
    const companyId = `m2-acceptance-${randomUUID()}`;
    const oldToken = process.env.FIRSTWEEK_SERVICE_TOKEN;
    const oldURL = process.env.FIRSTWEEK_RAG_URL;
    let server, ragServer;
    const calls = [];
    const listen = app => new Promise(resolve => { const value = app.listen(0, '127.0.0.1', () => resolve(value)); });
    try {
      assert.equal((await prisma.$queryRaw`SELECT current_database() AS name`)[0].name, 'firstweek_demo');
      await prisma.company.create({ data: { id: companyId, name: 'M2 acceptance fixture', allowedDomains: [] } });
      const [admin, memberA, memberB] = await Promise.all([
        ['admin', 'Admin', 'COMPANY_ADMIN'], ['member-a', 'Alex', 'EMPLOYEE'], ['member-b', 'Blair', 'EMPLOYEE'],
      ].map(([name, firstName, role]) => prisma.user.create({ data: { username: `${companyId}-${name}`, firstName,
        lastName: 'Fixture', password: 'not-a-login-hash', companyId, role, isActive: true,
        isCompanyVerified: true, emailVerified: true } })));
      const actors = new Map([admin, memberA, memberB].map(actor => [actor.id, actor]));
      const project = await createProject(prisma, admin, { name: 'M2 integrated acceptance' });
      await manageProject(prisma, admin, project.id, 'add', { username: memberA.username, role: 'MEMBER' });
      await manageProject(prisma, admin, project.id, 'add', { username: memberB.username, role: 'MEMBER' });
      const document = await documents.createDocument(prisma, admin, project.id, { filename: 'm2-acceptance.md',
        title: 'M2 acceptance source', content: '# Launch telemetry\nThe M2-04 launch telemetry runbook uses green dashboards.' });
      const engineering = await paths.saveStep(prisma, admin, project.id, { title: 'Engineering launch telemetry',
        description: 'Read the engineering runbook.', documentId: document.id, focus: 'ENGINEERING', experience: 'NEW' });
      const product = await paths.saveStep(prisma, admin, project.id, { title: 'Product launch telemetry',
        description: 'Read the product runbook.', documentId: document.id, focus: 'PRODUCT', experience: 'NEW' });
      await profiles.saveProfile(prisma, memberA, project.id, { onboardingRole: 'ENGINEERING', onboardingExperience: 'NEW' });
      await profiles.saveProfile(prisma, memberB, project.id, { onboardingRole: 'PRODUCT', onboardingExperience: 'NEW' });
      await paths.completeStep(prisma, memberA, project.id, engineering.id, { revision: engineering.revision });
      await paths.completeStep(prisma, memberB, project.id, product.id, { revision: product.revision });
      const team = await teams.saveTeam(prisma, admin, { name: 'Launch telemetry', description: 'Maintained integration team.' });
      const oldAssignment = 'M2-04 integration captain for launch telemetry';
      await teams.assignMember(prisma, admin, team.id, { username: memberA.username, assignment: oldAssignment });

      const rag = express(); rag.use(express.json());
      rag.post('/internal/firstweek/:company/:project/ask', (req, res) => {
        calls.push(req.body);
        const evidence = [...req.body.companySources, ...req.body.managedSources];
        return res.json({ answer: evidence.length ? evidence.map(item => item.content).join('\n') : 'No matching evidence was found.',
          sources: evidence, mode: 'source-excerpts' });
      });
      ragServer = await listen(rag);
      process.env.FIRSTWEEK_SERVICE_TOKEN = 'm2-acceptance-test-token-at-least-32';
      process.env.FIRSTWEEK_RAG_URL = `http://127.0.0.1:${ragServer.address().port}`;
      const app = express(); app.use(express.json()); app.use((req, res, next) => {
        req.user = actors.get(req.get('x-test-user'));
        return req.user ? next() : res.status(401).end();
      });
      app.use('/projects/:projectId/conversations', require('../routes/conversationRoutes')(prisma, (req, res, next) => {
        if (req.get('origin') !== 'http://workspace.test') return res.status(403).end();
        return next();
      }));
      server = await listen(app);
      const base = `http://127.0.0.1:${server.address().port}/projects/${project.id}/conversations`;
      const request = (actor, suffix = '', method = 'GET', body) => fetch(base + suffix, { method,
        headers: { 'x-test-user': actor.id, Origin: 'http://workspace.test', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
      const createConversation = async actor => (await (await request(actor, '', 'POST', {})).json()).id;
      const ask = (actor, conversationId, question) => request(actor, `/${conversationId}/turns`, 'POST', { question, requestId: randomUUID() });
      const read = async (actor, conversationId) => (await request(actor, `/${conversationId}`)).json();

      const conversationA = await createConversation(memberA);
      const conversationB = await createConversation(memberB);
      const question = 'What does the M2-04 launch telemetry integration captain use?';
      assert.equal((await ask(memberA, conversationA, question)).status, 200);
      assert.equal((await ask(memberB, conversationB, question)).status, 200);
      assert.deepEqual(calls[0].onboardingProfile, { onboardingRole: 'ENGINEERING', onboardingExperience: 'NEW', profileVersion: 1 });
      assert.ok(calls[0].managedSources.some(source => source.content.includes('green dashboards')));
      const assignment = calls[0].companySources.find(source => source.content.includes(oldAssignment));
      assert.ok(assignment?.updatedAt);
      assert.match(assignment.content, /not proof of a project responsibility or project access/i);
      assert.equal((await request(memberB, `/${conversationA}`)).status, 404);

      await profiles.saveProfile(prisma, memberA, project.id, { onboardingRole: 'PRODUCT', onboardingExperience: 'NEW' });
      assert.equal((await read(memberA, conversationA)).turns.length, 0);
      assert.equal((await read(memberB, conversationB)).turns.length, 1);
      const hidden = await paths.readPath(prisma, memberA, project.id);
      assert.equal(hidden.total, 1); assert.equal(hidden.completed, 0);
      assert.equal(hidden.steps[0].id, product.id); // Blair's completion is not Alex's completion.
      await profiles.saveProfile(prisma, memberA, project.id, { onboardingRole: 'ENGINEERING', onboardingExperience: 'NEW' });
      const restored = await paths.readPath(prisma, memberA, project.id);
      assert.equal(restored.total, 1); assert.equal(restored.completed, 1); assert.equal(restored.steps[0].id, engineering.id);
      assert.equal((await paths.readPath(prisma, memberB, project.id)).completed, 1);
      assert.equal(await prisma.projectReadingProgress.count({ where: { companyId, projectId: project.id } }), 2);
      assert.deepEqual((await prisma.projectMember.findMany({ where: { companyId, projectId: project.id },
        orderBy: { userId: 'asc' }, select: { userId: true, role: true } })).map(row => row.role).sort(), ['MAINTAINER', 'MEMBER', 'MEMBER']);

      const freshA = await createConversation(memberA);
      assert.equal((await ask(memberA, freshA, question)).status, 200);
      assert.match((await read(memberA, freshA)).turns[0].answer, new RegExp(oldAssignment));
      const newAssignment = 'M2-04 release liaison for launch telemetry';
      await teams.assignMember(prisma, admin, team.id, { username: memberA.username, assignment: newAssignment });
      assert.equal((await read(memberA, freshA)).turns.length, 0);
      assert.equal((await read(memberB, conversationB)).turns.length, 0);
      const edited = await createConversation(memberA);
      assert.equal((await ask(memberA, edited, question)).status, 200);
      const editedTurn = (await read(memberA, edited)).turns[0];
      assert.match(editedTurn.answer, new RegExp(newAssignment));
      assert.doesNotMatch(editedTurn.answer, new RegExp(oldAssignment));

      await teams.assignMember(prisma, admin, team.id, { username: memberA.username }, true);
      assert.equal((await read(memberA, edited)).turns.length, 0);
      assert.deepEqual(await profiles.readProfile(prisma, memberA, project.id),
        { onboardingRole: 'ENGINEERING', onboardingExperience: 'NEW', profileVersion: 3 });
      assert.equal((await paths.readPath(prisma, memberA, project.id)).completed, 1);
      assert.equal((await paths.readPath(prisma, memberB, project.id)).completed, 1);
      const unsupported = await createConversation(memberA);
      assert.equal((await ask(memberA, unsupported, 'Who owns the zqxj subsystem?')).status, 200);
      const unsupportedTurn = (await read(memberA, unsupported)).turns[0];
      assert.equal(unsupportedTurn.answer, 'No matching evidence was found.');
      assert.deepEqual(unsupportedTurn.sources, []);
      assert.equal(calls.at(-1).companySources.length, 0);
      assert.equal(calls.at(-1).managedSources.length, 0);
      assert.equal(await prisma.projectMember.count({ where: { companyId, projectId: project.id } }), 3);
    } finally {
      if (server) await new Promise(resolve => server.close(resolve));
      if (ragServer) await new Promise(resolve => ragServer.close(resolve));
      if (oldToken === undefined) delete process.env.FIRSTWEEK_SERVICE_TOKEN; else process.env.FIRSTWEEK_SERVICE_TOKEN = oldToken;
      if (oldURL === undefined) delete process.env.FIRSTWEEK_RAG_URL; else process.env.FIRSTWEEK_RAG_URL = oldURL;
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.companyTeam.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });
