const { randomUUID } = require('node:crypto');
const { findProjectMembership } = require('./projectAccess');

function fail(status, message) { throw Object.assign(new Error(message), { status }); }
function input(body) {
  if (!body || Array.isArray(body) || typeof body !== 'object' ||
      Object.keys(body).some(key => !['name', 'description', 'status', 'ownerUserId'].includes(key)) ||
      typeof body.name !== 'string' || !body.name.trim() || body.name.length > 120 ||
      typeof (body.description ?? '') !== 'string' || (body.description ?? '').length > 2000 ||
      !['ACTIVE', 'BLOCKED', 'DONE'].includes(body.status ?? 'ACTIVE') ||
      (![undefined, null].includes(body.ownerUserId) && typeof body.ownerUserId !== 'string')) {
    fail(400, 'Responsibility fields are invalid.');
  }
  return { name: body.name.trim(), description: (body.description ?? '').trim(),
    status: body.status ?? 'ACTIVE', ownerUserId: body.ownerUserId || null };
}
async function listResponsibilities(prisma, actor, projectId) {
  if (!await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  const rows = await prisma.projectResponsibility.findMany({ where: { companyId: actor.companyId, projectId },
    include: { assignment: { include: { owner: { include: { user: { select: { username: true, firstName: true, lastName: true, isActive: true, isCompanyVerified: true } } } } } } },
    orderBy: [{ status: 'asc' }, { name: 'asc' }] });
  if (!await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  return rows.map(({ assignment, ...row }) => {
    const owner = assignment?.owner?.user;
    const current = owner?.isActive && owner?.isCompanyVerified ? owner : null;
    return { ...row, owner: current, ownerUserId: current ? assignment.ownerUserId : null };
  });
}
async function saveResponsibility(prisma, actor, projectId, body, responsibilityId) {
  const data = input(body);
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    const membership = await findProjectMembership(tx, actor, projectId);
    if (!membership) fail(404, 'Project resource not found.');
    if (membership.role !== 'MAINTAINER') fail(403, 'Only project maintainers can manage responsibilities.');
    await tx.project.update({ where: { companyId_id: { companyId: actor.companyId, id: projectId } }, data: { knowledgeVersion: { increment: 1 } } });
    const scope = { companyId: actor.companyId, projectId };
    if (data.ownerUserId && !await tx.projectMember.findFirst({ where: { ...scope, userId: data.ownerUserId,
      user: { isActive: true, isCompanyVerified: true } } })) {
      fail(400, 'Owner must be a current project member.');
    }
    const id = responsibilityId || `r-${randomUUID()}`;
    const responsibility = responsibilityId
      ? await tx.projectResponsibility.update({ where: { companyId_projectId_id: { ...scope, id } }, data: { name: data.name, description: data.description, status: data.status } })
      : await tx.projectResponsibility.create({ data: { ...scope, id, name: data.name, description: data.description, status: data.status } });
    await tx.responsibilityAssignment.deleteMany({ where: { ...scope, responsibilityId: id } });
    if (data.ownerUserId) await tx.responsibilityAssignment.create({ data: { ...scope, responsibilityId: id, ownerUserId: data.ownerUserId } });
    return responsibility;
  });
}
async function deleteResponsibility(prisma, actor, projectId, responsibilityId) {
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    const membership = await findProjectMembership(tx, actor, projectId);
    if (!membership) fail(404, 'Project resource not found.');
    if (membership.role !== 'MAINTAINER') fail(403, 'Only project maintainers can manage responsibilities.');
    await tx.project.update({ where: { companyId_id: { companyId: actor.companyId, id: projectId } }, data: { knowledgeVersion: { increment: 1 } } });
    return tx.projectResponsibility.delete({ where: { companyId_projectId_id: { companyId: actor.companyId, projectId, id: responsibilityId } } });
  });
}
module.exports = { listResponsibilities, saveResponsibility, deleteResponsibility };
