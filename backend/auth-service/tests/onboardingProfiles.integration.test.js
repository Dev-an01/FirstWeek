const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');
const { readProfile, saveProfile } = require('../services/onboardingProfiles');
const conversations = require('../services/projectConversations');

test('private onboarding preferences persist, preserve permissions and fence only own history',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const companyId = `profiles-${randomUUID()}`;
    const empty = { onboardingRole: null, onboardingExperience: null };
    try {
      await prisma.company.create({ data: { id: companyId, name: 'Profile test', allowedDomains: [] } });
      const [admin, member, outsider] = await Promise.all(['admin', 'member', 'outsider'].map((name, i) => prisma.user.create({ data: {
        username: `${companyId}-${name}`, firstName: name, lastName: 'Test', password: 'not-a-login-hash', companyId,
        role: i ? 'EMPLOYEE' : 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } })));
      const p = await createProject(prisma, admin, { name: 'Onboarding' });
      await manageProject(prisma, admin, p.id, 'add', { username: member.username, role: 'MEMBER' });
      assert.deepEqual(await readProfile(prisma, member, p.id), { ...empty, profileVersion: 0 });
      for (const actor of [outsider, { ...member, companyId: 'other' }, { ...member, isActive: false }]) {
        await assert.rejects(readProfile(prisma, actor, p.id), { status: 404 });
        await assert.rejects(saveProfile(prisma, actor, p.id, empty), { status: 404 });
      }
      for (const body of [{}, [], { ...empty, userId: admin.id }, { ...empty, role: 'MAINTAINER' },
        { ...empty, onboardingRole: 'SUPER_ADMIN' }, { ...empty, onboardingExperience: '' }]) {
        await assert.rejects(saveProfile(prisma, member, p.id, body), { status: 400 });
      }
      const version = (await prisma.project.findUnique({ where: { companyId_id: { companyId, id: p.id } } })).knowledgeVersion;
      const snapshot = { hash: 'before-profile', version, profileVersion: 0 };
      const a = await conversations.createConversation(prisma, admin, p.id, snapshot);
      const m = await conversations.createConversation(prisma, member, p.id, snapshot);
      const request = { question: 'Saved question', requestId: randomUUID() };
      const pendingAdmin = (await conversations.beginTurn(prisma, admin, p.id, a.id, snapshot, request)).conversation;
      const pendingMember = (await conversations.beginTurn(prisma, member, p.id, m.id, snapshot, request)).conversation;
      const answer = { answer: 'Saved answer', sources: [] };
      await conversations.finishTurn(prisma, member, p.id, pendingMember, snapshot, answer);
      const oldWorker = (await conversations.beginTurn(prisma, member, p.id, m.id, snapshot, { ...request, requestId: randomUUID() })).conversation;
      const choice = { onboardingRole: 'ENGINEERING', onboardingExperience: 'NEW' };
      assert.deepEqual(await saveProfile(prisma, member, p.id, choice), { ...choice, profileVersion: 1 });
      assert.deepEqual(await saveProfile(prisma, member, p.id, choice), { ...choice, profileVersion: 1 });
      await prisma.$disconnect();
      assert.deepEqual(await readProfile(prisma, member, p.id), { ...choice, profileVersion: 1 });
      assert.equal((await prisma.projectMember.findFirst({ where: { companyId, projectId: p.id, userId: member.id } })).role, 'MEMBER');
      assert.equal((await prisma.user.findUnique({ where: { id: member.id } })).role, 'EMPLOYEE');
      const cleared = await prisma.projectConversation.findFirst({ where: { companyId, id: m.id } });
      assert.deepEqual(cleared.turns, []); assert.equal(cleared.pendingQuestion, null); assert.equal(cleared.pendingId, null);
      await assert.rejects(conversations.beginTurn(prisma, member, p.id, m.id, snapshot, request), { status: 409 });
      await assert.rejects(conversations.finishTurn(prisma, member, p.id, oldWorker, snapshot, answer), { status: 409 });
      await assert.rejects(conversations.finishTurn(prisma, member, p.id, oldWorker, { ...snapshot, profileVersion: 1 }, answer), { status: 409 });
      await conversations.finishTurn(prisma, admin, p.id, pendingAdmin, snapshot, answer);
      assert.equal((await conversations.readConversation(prisma, admin, p.id, a.id, snapshot)).turns.length, 1);
      assert.deepEqual(await readProfile(prisma, admin, p.id), { ...empty, profileVersion: 0 });
      assert.deepEqual(await saveProfile(prisma, member, p.id, empty), { ...empty, profileVersion: 2 });
      await manageProject(prisma, admin, p.id, 'remove', {}, member.id);
      await assert.rejects(readProfile(prisma, member, p.id), { status: 404 });
      await manageProject(prisma, admin, p.id, 'add', { username: member.username, role: 'MEMBER' });
      assert.deepEqual(await readProfile(prisma, member, p.id), { ...empty, profileVersion: 0 });
      assert.equal(await prisma.projectConversation.count({ where: { companyId, userId: member.id } }), 0);
    } finally {
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });
