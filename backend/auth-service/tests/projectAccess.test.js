const { test } = require('node:test');
const assert = require('node:assert/strict');
const { projectScope, findProjectMembership } = require('../services/projectAccess');
const user = { id: 'member-a', companyId: 'company-a', isActive: true, isCompanyVerified: true };

test('missing identity, unverified company and invalid project IDs fail closed', () => {
  for (const identity of [null, {}, { ...user, companyId: null }, { ...user, isActive: false }, { ...user, isCompanyVerified: false }]) {
    assert.equal(projectScope(identity, 'alpha'), null);
  }
  for (const id of [undefined, '../beta', 'alpha/beta', '', ['alpha']]) assert.equal(projectScope(user, id), null);
});

test('scope comes from authenticated identity and has no admin bypass', async () => {
  let captured;
  const prisma = { projectMember: { findFirst: async (query) => { captured = query; return null; } } };
  const result = await findProjectMembership(prisma, { ...user, role: 'SUPER_ADMIN' }, 'alpha');
  assert.equal(result, null);
  assert.deepEqual(captured.where, { companyId: 'company-a', projectId: 'alpha', userId: 'member-a',
    project: { isActive: true }, user: { isActive: true, isCompanyVerified: true } });
});

test('revocation is checked with a fresh database read', async () => {
  let active = true;
  const prisma = { projectMember: { findFirst: async () => active ? { project: { id: 'alpha' } } : null } };
  assert.ok(await findProjectMembership(prisma, user, 'alpha'));
  active = false;
  assert.equal(await findProjectMembership(prisma, user, 'alpha'), null);
});
