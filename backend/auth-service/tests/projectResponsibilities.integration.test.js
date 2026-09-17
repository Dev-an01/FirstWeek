const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

test('responsibility owners stay project-scoped and removal leaves records unassigned',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const { listResponsibilities, saveResponsibility } = require('../services/projectResponsibilities');
    const companyId = `ownership-${randomUUID()}`;
    try {
      await prisma.company.create({ data: { id: companyId, name: 'Ownership test', allowedDomains: [] } });
      const users = await Promise.all(['admin', 'owner', 'other', 'inactive'].map((name, index) => prisma.user.create({ data: {
        username: `${companyId}-${name}`, firstName: name, lastName: 'Test', password: 'not-a-login-hash',
        companyId, role: index ? 'EMPLOYEE' : 'COMPANY_ADMIN', isActive: name !== 'inactive', isCompanyVerified: true, emailVerified: true } })));
      const [admin, owner, other, inactive] = users;
      const project = await createProject(prisma, admin, { name: 'Ownership' });
      await manageProject(prisma, admin, project.id, 'add', { username: owner.username, role: 'MEMBER' });
      await assert.rejects(saveResponsibility(prisma, admin, project.id,
        { name: 'Deployments', status: 'ACTIVE', ownerUserId: other.id }), { status: 400 });
      await prisma.projectMember.create({ data: { companyId, projectId: project.id, userId: inactive.id, role: 'MEMBER' } });
      await assert.rejects(saveResponsibility(prisma, admin, project.id,
        { name: 'Inactive', status: 'ACTIVE', ownerUserId: inactive.id }), { status: 400 });
      await saveResponsibility(prisma, admin, project.id,
        { name: 'Deployments', description: 'Own release readiness', status: 'ACTIVE', ownerUserId: owner.id });
      assert.equal((await listResponsibilities(prisma, owner, project.id))[0].ownerUserId, owner.id);
      await assert.rejects(saveResponsibility(prisma, owner, project.id,
        { name: 'Denied', status: 'ACTIVE', ownerUserId: owner.id }), { status: 403 });
      const race = await Promise.allSettled([
        saveResponsibility(prisma, admin, project.id, { name: 'Deployments', status: 'BLOCKED', ownerUserId: owner.id },
          (await listResponsibilities(prisma, admin, project.id))[0].id),
        manageProject(prisma, admin, project.id, 'remove', {}, owner.id),
      ]);
      assert.ok(race.some(result => result.status === 'fulfilled'));
      const retained = (await listResponsibilities(prisma, admin, project.id))[0];
      assert.equal(retained.name, 'Deployments'); assert.equal(retained.owner, null); assert.equal(retained.ownerUserId, null);
    } finally {
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });
