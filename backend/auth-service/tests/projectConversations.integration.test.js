const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

test('private conversations persist, fence concurrent workers and invalidate deleted knowledge',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const { createDocument, deleteDocument } = require('../services/projectDocuments');
    const s = require('../services/projectConversations');
    const companyId = `conversations-${randomUUID()}`;
    try {
      await prisma.company.create({ data: { id: companyId, name: 'Conversation test', allowedDomains: [] } });
      const [admin, member] = await Promise.all(['admin', 'member'].map((name, i) => prisma.user.create({ data: {
        username: `${companyId}-${name}`, firstName: name, lastName: 'Test', password: 'not-a-login-hash', companyId,
        role: i ? 'EMPLOYEE' : 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } })));
      const p = await createProject(prisma, admin, { name: 'Conversations' });
      await manageProject(prisma, admin, p.id, 'add', { username: member.username, role: 'MEMBER' });
      const snapshot = async hash => ({ hash, version: (await prisma.project.findUnique({ where: { companyId_id: { companyId, id: p.id } } })).knowledgeVersion });
      let hash = await snapshot('knowledge-v1');
      const c = await s.createConversation(prisma, admin, p.id, hash);
      await assert.rejects(s.readConversation(prisma, member, p.id, c.id, hash), { status: 404 });
      await assert.rejects(s.deleteConversation(prisma, member, p.id, c.id), { status: 404 });
      await assert.rejects(s.readConversation(prisma, { ...admin, companyId: 'other' }, p.id, c.id, hash), { status: 404 });
      const request = { question: 'What is the secret beacon?', requestId: randomUUID() };
      const starts = await Promise.allSettled([s.beginTurn(prisma, admin, p.id, c.id, hash, request),
        s.beginTurn(prisma, admin, p.id, c.id, hash, { ...request, requestId: randomUUID() })]);
      assert.equal(starts.filter(r => r.status === 'fulfilled').length, 1);
      const reserved = starts.find(r => r.status === 'fulfilled').value.conversation;
      const answer = { answer: 'Private beacon [1]', sources: [{ content: 'Private beacon', documentId: 'doc' }], mode: 'generated' };
      const complete = await s.finishTurn(prisma, admin, p.id, reserved, hash, answer);
      assert.equal(complete.turns.length, 1);
      const retry = await s.beginTurn(prisma, admin, p.id, c.id, hash, { question: reserved.pendingQuestion, requestId: reserved.pendingId });
      assert.equal(retry.completed.turns.length, 1);
      await assert.rejects(s.beginTurn(prisma, admin, p.id, c.id, hash, { question: 'Different', requestId: reserved.pendingId }), { status: 409 });
      await assert.rejects(s.beginTurn(prisma, admin, p.id, c.id, hash, { ...request, history: [] }), { status: 400 });
      await prisma.$disconnect();
      assert.equal((await s.readConversation(prisma, admin, p.id, c.id, hash)).turns[0].answer, answer.answer);
      const old = (await s.beginTurn(prisma, admin, p.id, c.id, hash, { question: 'Follow up', requestId: randomUUID() })).conversation;
      await prisma.projectConversation.updateMany({ where: { companyId, id: c.id }, data: { pendingAt: new Date(Date.now() - 61000) } });
      const fresh = (await s.beginTurn(prisma, admin, p.id, c.id, hash, { question: 'Retry follow up', requestId: randomUUID() })).conversation;
      await assert.rejects(s.finishTurn(prisma, admin, p.id, old, hash, answer), { status: 409 });
      await s.failTurn(prisma, admin, p.id, old);
      assert.equal((await s.readConversation(prisma, admin, p.id, c.id, hash)).pendingId, fresh.pendingId);
      await s.failTurn(prisma, admin, p.id, fresh);
      hash = await snapshot('curated-changed');
      assert.equal((await s.readConversation(prisma, admin, p.id, c.id, hash)).turns.length, 0);
      assert.ok(!(await s.listConversations(prisma, admin, p.id, hash))[0].title.includes('beacon'));
      const doc = await createDocument(prisma, admin, p.id, { filename: 'source.md', content: 'Private beacon' });
      hash = await snapshot('with-document');
      const mc = await s.createConversation(prisma, member, p.id, hash);
      const pending = (await s.beginTurn(prisma, admin, p.id, c.id, hash, { question: 'Private beacon', requestId: randomUUID() })).conversation;
      const mp = (await s.beginTurn(prisma, member, p.id, mc.id, hash, { question: 'Private beacon', requestId: randomUUID() })).conversation;
      await s.finishTurn(prisma, member, p.id, mp, hash, answer);
      await deleteDocument(prisma, admin, p.id, doc.id);
      const rows = await prisma.projectConversation.findMany({ where: { companyId } });
      assert.ok(rows.every(row => row.turns.length === 0 && row.pendingQuestion === null && !row.title.includes('beacon')));
      await assert.rejects(s.finishTurn(prisma, admin, p.id, pending, await snapshot('deleted'), answer), { status: 409 });
      await manageProject(prisma, admin, p.id, 'remove', {}, member.id);
      assert.equal(await prisma.projectConversation.count({ where: { companyId, userId: member.id } }), 0);
      await assert.rejects(s.finishTurn(prisma, member, p.id, mp, await snapshot('removed'), answer), { status: 404 });
      await s.deleteConversation(prisma, admin, p.id, c.id);
      await assert.rejects(s.readConversation(prisma, admin, p.id, c.id, await snapshot('deleted')), { status: 404 });
    } finally {
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });
