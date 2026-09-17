const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

test('reading paths keep ordered managed sources and private revision-fenced progress',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const paths = require('../services/readingPaths');
    const documents = require('../services/projectDocuments');
    const { saveProfile } = require('../services/onboardingProfiles');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const companyId = `reading-${randomUUID()}`;
    let project, admin, member, outsider;
    try {
      await prisma.company.create({ data: { id: companyId, name: 'Reading test', allowedDomains: [] } });
      [admin, member, outsider] = await Promise.all(['admin', 'member', 'outsider'].map((name, index) => prisma.user.create({ data: {
        username: `${companyId}-${name}`, firstName: name, lastName: 'Test', password: 'not-a-login-hash', companyId,
        role: index ? 'EMPLOYEE' : 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } })));
      project = await createProject(prisma, admin, { name: 'Reading paths' });
      await manageProject(prisma, admin, project.id, 'add', { username: member.username, role: 'MEMBER' });
      await saveProfile(prisma, member, project.id, { onboardingRole: 'ENGINEERING', onboardingExperience: null });
      const doc = await documents.createDocument(prisma, admin, project.id, { filename: 'one.md', title: 'One', content: '# One\nManaged source one.' });
      const secondDoc = await documents.createDocument(prisma, admin, project.id, { filename: 'two.md', title: 'Two', content: '# Two\nManaged source two.' });
      const thirdDoc = await documents.createDocument(prisma, admin, project.id, { filename: 'three.md', title: 'Three', content: '# Three\nManaged source three.' });
      const first = await paths.saveStep(prisma, admin, project.id, { title: 'Read one', description: '', documentId: doc.id, focus: 'ENGINEERING', experience: null });
      const second = await paths.saveStep(prisma, admin, project.id, { title: 'Read two', description: '', documentId: secondDoc.id, focus: null, experience: null });
      const third = await paths.saveStep(prisma, admin, project.id, { title: 'Read three', description: '', documentId: thirdDoc.id, focus: 'DESIGN', experience: 'EXPERIENCED' });
      for (const action of [
        () => paths.saveStep(prisma, member, project.id, { title: 'Nope', description: '', documentId: doc.id, focus: null, experience: null }),
        () => paths.removeStep(prisma, member, project.id, first.id),
        () => paths.reorderSteps(prisma, member, project.id, { stepIds: [first.id, second.id, third.id] }),
      ]) await assert.rejects(action(), { status: 403 });
      await assert.rejects(paths.saveStep(prisma, admin, project.id, { title: 'Injected', description: '', documentId: doc.id, focus: null, experience: null, companyId: 'other' }), { status: 400 });
      await assert.rejects(paths.completeStep(prisma, member, project.id, first.id, { revision: first.revision, userId: admin.id }), { status: 400 });
      await assert.rejects(paths.reorderSteps(prisma, admin, project.id, { stepIds: [first.id, second.id, third.id], projectId: 'other' }), { status: 400 });
      await assert.rejects(paths.saveStep(prisma, admin, project.id, { title: 'Wrong scope', description: '', documentId: 'm-not-a-document', focus: null, experience: null }), { status: 404 });
      await assert.rejects(paths.reorderSteps(prisma, admin, project.id, { stepIds: [first.id, first.id] }), { status: 400 });
      await assert.rejects(paths.reorderSteps(prisma, admin, project.id, { stepIds: [first.id] }), { status: 409 });
      await paths.reorderSteps(prisma, admin, project.id, { stepIds: [second.id, first.id, third.id] });
      assert.deepEqual((await paths.readPath(prisma, admin, project.id)).managedSteps.map(step => step.id), [second.id, first.id, third.id]);
      await paths.completeStep(prisma, member, project.id, first.id, { revision: first.revision });
      assert.equal((await paths.readPath(prisma, member, project.id)).completed, 1);
      const changed = await paths.saveStep(prisma, admin, project.id, { title: 'Read one revised', description: 'Material edit', documentId: doc.id, focus: 'ENGINEERING', experience: null }, first.id);
      assert.equal((await paths.readPath(prisma, member, project.id)).completed, 0);
      await assert.rejects(paths.completeStep(prisma, member, project.id, first.id, { revision: first.revision }), { status: 409 });
      await paths.completeStep(prisma, member, project.id, first.id, { revision: changed.revision });
      const memberPath = await paths.readPath(prisma, member, project.id);
      assert.equal(memberPath.completed, 1); assert.equal(memberPath.total, 2);
      const adminPath = await paths.readPath(prisma, admin, project.id);
      assert.equal(adminPath.completed, 0); // Completion belongs only to the requesting member.
      assert.equal(adminPath.steps.length, 1); assert.equal(adminPath.managedSteps.length, 3);
      await saveProfile(prisma, member, project.id, { onboardingRole: null, onboardingExperience: null });
      assert.equal((await paths.readPath(prisma, member, project.id)).total, 1);
      await saveProfile(prisma, member, project.id, { onboardingRole: 'ENGINEERING', onboardingExperience: null });
      await assert.rejects(paths.readPath(prisma, outsider, project.id), { status: 404 });
      await paths.completeStep(prisma, member, project.id, second.id, { revision: second.revision });
      await documents.deleteDocument(prisma, admin, project.id, secondDoc.id);
      assert.equal(await prisma.projectReadingStep.count({ where: { companyId, projectId: project.id, id: second.id } }), 0);
      assert.equal(await prisma.projectReadingProgress.count({ where: { companyId, projectId: project.id, stepId: second.id } }), 0);
      await prisma.$disconnect();
      const reconnected = await paths.readPath(prisma, member, project.id);
      assert.equal(reconnected.completed, 1);
      assert.equal(reconnected.steps.find(step => step.id === first.id).revision, changed.revision);
      const appended = await paths.saveStep(prisma, admin, project.id, { title: 'Append after source deletion', description: '', documentId: doc.id, focus: null, experience: null });
      assert.ok(appended.position > changed.position);
      await manageProject(prisma, admin, project.id, 'remove', {}, member.id);
      assert.equal(await prisma.projectReadingProgress.count({ where: { companyId, projectId: project.id, userId: member.id } }), 0);
      await assert.rejects(paths.readPath(prisma, member, project.id), { status: 404 });
      assert.equal((await paths.readPath(prisma, admin, project.id)).managedSteps.length, 3);
    } finally {
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });

test('reading-path project locks preserve quotas and revision truth under competing writes',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const paths = require('../services/readingPaths');
    const documents = require('../services/projectDocuments');
    const { saveProfile } = require('../services/onboardingProfiles');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const companyId = `reading-race-${randomUUID()}`;
    const foreignCompanyId = `reading-foreign-${randomUUID()}`;
    let project, sameCompanyProject, foreignProject, admin, member, foreignAdmin;
    try {
      await prisma.company.createMany({ data: [
        { id: companyId, name: 'Reading race test', allowedDomains: [] },
        { id: foreignCompanyId, name: 'Foreign reading test', allowedDomains: [] },
      ] });
      [admin, member, foreignAdmin] = await Promise.all([
        prisma.user.create({ data: { username: `${companyId}-admin`, firstName: 'admin', lastName: 'Test', password: 'not-a-login-hash', companyId, role: 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } }),
        prisma.user.create({ data: { username: `${companyId}-member`, firstName: 'member', lastName: 'Test', password: 'not-a-login-hash', companyId, role: 'EMPLOYEE', isActive: true, isCompanyVerified: true, emailVerified: true } }),
        prisma.user.create({ data: { username: `${foreignCompanyId}-admin`, firstName: 'foreign', lastName: 'Test', password: 'not-a-login-hash', companyId: foreignCompanyId, role: 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } }),
      ]);
      project = await createProject(prisma, admin, { name: 'Reading races' });
      sameCompanyProject = await createProject(prisma, admin, { name: 'Sibling reading' });
      foreignProject = await createProject(prisma, foreignAdmin, { name: 'Foreign reading' });
      await manageProject(prisma, admin, project.id, 'add', { username: member.username, role: 'MEMBER' });
      const doc = await documents.createDocument(prisma, admin, project.id, { filename: 'race.md', title: 'Race', content: '# Race\nLocal source.' });
      const siblingDoc = await documents.createDocument(prisma, admin, sameCompanyProject.id, { filename: 'sibling.md', title: 'Sibling', content: '# Sibling\nSame company, different project.' });
      const foreignDoc = await documents.createDocument(prisma, foreignAdmin, foreignProject.id, { filename: 'foreign.md', title: 'Foreign', content: '# Foreign\nForeign source.' });
      await assert.rejects(paths.saveStep(prisma, admin, project.id, { title: 'Cross project', description: '', documentId: siblingDoc.id, focus: null, experience: null }), { status: 404 });
      await assert.rejects(paths.saveStep(prisma, admin, project.id, { title: 'Cross company', description: '', documentId: foreignDoc.id, focus: null, experience: null }), { status: 404 });

      const filtered = await paths.saveStep(prisma, admin, project.id, { title: 'Design only', description: '', documentId: doc.id, focus: 'DESIGN', experience: 'EXPERIENCED' });
      assert.equal((await paths.readPath(prisma, member, project.id)).total, 0);
      assert.equal((await paths.readPath(prisma, admin, project.id)).managedSteps.length, 1);
      await prisma.projectReadingStep.delete({ where: { companyId_projectId_id: { companyId, projectId: project.id, id: filtered.id } } });

      await prisma.projectReadingStep.createMany({ data: Array.from({ length: 49 }, (_, position) => ({
        companyId, projectId: project.id, id: `r-${randomUUID()}`, title: `Quota ${position}`, description: '', documentId: doc.id, position,
      })) });
      const quotaResults = await Promise.allSettled(['A', 'B'].map(title => paths.saveStep(prisma, admin, project.id,
        { title: `Quota ${title}`, description: '', documentId: doc.id, focus: null, experience: null })));
      assert.equal(quotaResults.filter(result => result.status === 'fulfilled').length, 1);
      assert.equal(quotaResults.find(result => result.status === 'rejected').reason.status, 409);
      assert.equal(await prisma.projectReadingStep.count({ where: { companyId, projectId: project.id } }), 50);

      await prisma.projectReadingStep.deleteMany({ where: { companyId, projectId: project.id } });
      await saveProfile(prisma, member, project.id, { onboardingRole: 'ENGINEERING', onboardingExperience: null });
      const current = await paths.saveStep(prisma, admin, project.id, { title: 'Current', description: '', documentId: doc.id, focus: null, experience: null });
      const raceResults = await Promise.allSettled([
        paths.saveStep(prisma, admin, project.id, { title: 'Current revised', description: 'Changed', documentId: doc.id, focus: null, experience: null }, current.id),
        paths.completeStep(prisma, member, project.id, current.id, { revision: current.revision }),
      ]);
      assert.equal(raceResults[0].status, 'fulfilled');
      if (raceResults[1].status === 'rejected') assert.equal(raceResults[1].reason.status, 409);
      const afterRace = await paths.readPath(prisma, member, project.id);
      assert.equal(afterRace.steps[0].revision, 1);
      assert.equal(afterRace.completed, 0);

      const secondDoc = await documents.createDocument(prisma, admin, project.id, { filename: 'delete-race.md', title: 'Delete race', content: '# Delete\nDelete race source.' });
      const removable = await paths.saveStep(prisma, admin, project.id, { title: 'Removable', description: '', documentId: secondDoc.id, focus: null, experience: null });
      const reorderResults = await Promise.allSettled([
        paths.reorderSteps(prisma, admin, project.id, { stepIds: [removable.id, current.id] }),
        documents.deleteDocument(prisma, admin, project.id, secondDoc.id),
      ]);
      assert.equal(reorderResults[1].status, 'fulfilled');
      if (reorderResults[0].status === 'rejected') assert.equal(reorderResults[0].reason.status, 409);
      const remaining = await prisma.projectReadingStep.findMany({ where: { companyId, projectId: project.id }, select: { id: true, position: true } });
      assert.equal(remaining.length, 1);
      assert.equal(remaining[0].id, current.id);
      assert.ok(remaining[0].position >= 0);
      assert.equal(new Set(remaining.map(row => row.position)).size, remaining.length);
    } finally {
      await prisma.project.deleteMany({ where: { OR: [{ companyId }, { companyId: foreignCompanyId }] } });
      await prisma.user.deleteMany({ where: { companyId: { in: [companyId, foreignCompanyId] } } });
      await prisma.company.deleteMany({ where: { id: { in: [companyId, foreignCompanyId] } } });
      await prisma.$disconnect();
    }
  });
