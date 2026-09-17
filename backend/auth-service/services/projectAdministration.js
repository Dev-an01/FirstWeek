const { randomUUID } = require('node:crypto');
const { findProjectMembership } = require('./projectAccess');

function fail(status, message) {
  throw Object.assign(new Error(message), { status });
}
function fields(body, allowed, required = allowed) {
  if (!body || Array.isArray(body) || typeof body !== 'object' ||
      Object.keys(body).some(key => !allowed.includes(key)) || required.some(key => !(key in body))) {
    fail(400, 'Request fields are invalid.');
  }
}
function text(value, max, label, optional = false) {
  if (typeof value !== 'string' || value.length > max || (!optional && !value.trim())) {
    fail(400, `${label} must contain ${optional ? '0' : '1'}–${max} characters.`);
  }
  return value.trim();
}
function role(value) {
  if (!['MEMBER', 'MAINTAINER'].includes(value)) fail(400, 'Choose Member or Maintainer.');
  return value;
}
function projectInput(body) {
  fields(body, ['name', 'description'], ['name']);
  return { name: text(body.name, 120, 'Project name'), description: text(body.description ?? '', 2000, 'Description', true) };
}
async function createProject(prisma, actor, body) {
  const data = projectInput(body);
  return prisma.$transaction(async tx => {
    const user = await tx.user.findFirst({ where: { id: actor.id, companyId: actor.companyId,
      role: 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true } });
    if (!user) fail(403, 'Only company administrators can create projects.');
    return tx.project.create({ data: { ...data, companyId: user.companyId, id: `p-${randomUUID()}`,
      hasCuratedKnowledge: false, members: { create: { userId: user.id, role: 'MAINTAINER' } } } });
  });
}
async function manageProject(prisma, actor, projectId, action, body, userId) {
  let data;
  if (action === 'settings') data = projectInput(body);
  else if (action === 'add') {
    fields(body, ['username', 'role']);
    data = { username: text(body.username, 100, 'Username'), role: role(body.role) };
  } else if (action === 'role') { fields(body, ['role']); data = { role: role(body.role) }; }
  else fields(body, []);
  return prisma.$transaction(async tx => {
    // Every membership mutation takes the same row lock, then rechecks current authority.
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    const membership = await findProjectMembership(tx, actor, projectId);
    if (!membership) fail(404, 'Project resource not found.');
    if (membership.role !== 'MAINTAINER') fail(403, 'Only project maintainers can manage this project.');
    const scope = { companyId: actor.companyId, projectId };
    await tx.project.update({ where: { companyId_id: { companyId: actor.companyId, id: projectId } }, data: { knowledgeVersion: { increment: 1 } } });
    if (action === 'settings') return tx.project.update({ where: { companyId_id: { companyId: actor.companyId, id: projectId } }, data });
    if (action === 'add') {
      const target = await tx.user.findFirst({ where: { username: data.username, companyId: actor.companyId,
        isActive: true, isCompanyVerified: true, emailVerified: true }, select: { id: true } });
      if (!target) fail(404, 'No active, verified member with that exact username was found in your company.');
      const existing = await tx.projectMember.findUnique({ where: { companyId_projectId_userId: { ...scope, userId: target.id } } });
      if (existing) fail(409, 'This person already belongs to the project.');
      return tx.projectMember.create({ data: { ...scope, userId: target.id, role: data.role } });
    }
    const where = { companyId_projectId_userId: { ...scope, userId } };
    const target = await tx.projectMember.findUnique({ where });
    if (!target) fail(404, 'Project member not found.');
    if (target.role === 'MAINTAINER' && (action === 'remove' || data.role !== 'MAINTAINER')) {
      const maintainers = await tx.projectMember.count({ where: { ...scope, role: 'MAINTAINER',
        user: { isActive: true, isCompanyVerified: true } } });
      if (maintainers <= 1) fail(409, 'Keep at least one active maintainer. Add another maintainer first.');
    }
    if (action === 'remove') {
      await tx.responsibilityAssignment.deleteMany({ where: { ...scope, ownerUserId: userId } });
      return tx.projectMember.delete({ where });
    }
    return tx.projectMember.update({ where, data });
  }, { maxWait: 5000, timeout: 10000 });
}

module.exports = { createProject, manageProject };
