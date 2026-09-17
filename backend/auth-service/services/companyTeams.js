const { randomUUID } = require('node:crypto');
const { cleared } = require('./projectConversations');

function fail(status, message) { throw Object.assign(new Error(message), { status }); }
function fields(body, keys) {
  if (!body || typeof body !== 'object' || Array.isArray(body) ||
      Object.keys(body).length !== keys.length || keys.some(k => !Object.hasOwn(body, k))) {
    fail(400, 'Request fields are invalid.');
  }
}
function text(value, max, optional = false) {
  if (typeof value !== 'string' || value.length > max || (!optional && !value.trim()) ||
      /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\p{Surrogate}]/u.test(value)) {
    fail(400, `Text must contain ${optional ? '0' : '1'}–${max} valid characters.`);
  }
  return value.trim();
}
async function requireCompany(prisma, actor, admin = false) {
  if (!actor?.id || !actor.companyId || !actor.isActive || !actor.isCompanyVerified) fail(403, 'Verified company membership is required.');
  const user = await prisma.user.findFirst({ where: { id: actor.id, companyId: actor.companyId,
    isActive: true, isCompanyVerified: true, company: { isActive: true } }, select: { role: true } });
  if (!user || (admin && user.role !== 'COMPANY_ADMIN')) fail(403, admin
    ? 'Only current company administrators can maintain company teams.' : 'Verified company membership is required.');
  return user;
}
async function locked(prisma, actor, operation) {
  await requireCompany(prisma, actor, true);
  // ponytail: serialize bounded company-directory edits; use finer locks if admin throughput requires it.
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM companies WHERE id = ${actor.companyId} FOR UPDATE`;
    // Match conversation/project writers before changing any shared evidence.
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} ORDER BY id FOR UPDATE`;
    await requireCompany(tx, actor, true);
    const result = await operation(tx);
    await tx.project.updateMany({ where: { companyId: actor.companyId }, data: { knowledgeVersion: { increment: 1 } } });
    await tx.projectConversation.updateMany({ where: { companyId: actor.companyId }, data: {
      ...cleared, title: 'Conversation reset after company context changes', knowledgeHash: '', version: { increment: 1 } } });
    return result;
  }, { maxWait: 5000, timeout: 10000 });
}
async function listTeams(prisma, actor) {
  await requireCompany(prisma, actor);
  const teams = await prisma.companyTeam.findMany({ where: { companyId: actor.companyId }, orderBy: [{ name: 'asc' }, { id: 'asc' }],
    select: { id: true, name: true, description: true, updatedAt: true, assignments: {
      where: { user: { isActive: true, isCompanyVerified: true, emailVerified: true } }, orderBy: { user: { username: 'asc' } },
      select: { assignment: true, updatedAt: true, user: { select: { username: true, firstName: true, lastName: true } } } } } });
  const current = await requireCompany(prisma, actor);
  return { canManage: current.role === 'COMPANY_ADMIN', teams };
}
async function saveTeam(prisma, actor, body, teamId) {
  fields(body, ['name', 'description']);
  const data = { name: text(body.name, 120), description: text(body.description, 2000, true) };
  return locked(prisma, actor, async tx => {
    if (teamId && !await tx.companyTeam.findUnique({ where: { companyId_id: { companyId: actor.companyId, id: teamId } } })) fail(404, 'Company team not found.');
    const duplicate = await tx.companyTeam.findFirst({ where: { companyId: actor.companyId,
      name: { equals: data.name, mode: 'insensitive' }, ...(teamId ? { id: { not: teamId } } : {}) } });
    if (duplicate) fail(409, 'A company team with that name already exists.');
    if (!teamId && await tx.companyTeam.count({ where: { companyId: actor.companyId } }) >= 100) fail(409, 'A company can have at most 100 teams.');
    return teamId ? tx.companyTeam.update({ where: { companyId_id: { companyId: actor.companyId, id: teamId } }, data })
      : tx.companyTeam.create({ data: { ...data, companyId: actor.companyId, id: `t-${randomUUID()}` } });
  });
}
async function deleteTeam(prisma, actor, teamId, body) {
  fields(body, []);
  return locked(prisma, actor, async tx => {
    const result = await tx.companyTeam.deleteMany({ where: { companyId: actor.companyId, id: teamId } });
    if (!result.count) fail(404, 'Company team not found.');
    return { id: teamId };
  });
}
async function assignMember(prisma, actor, teamId, body, remove = false) {
  fields(body, remove ? ['username'] : ['username', 'assignment']);
  const username = text(body.username, 100);
  const assignment = remove ? null : text(body.assignment, 500);
  return locked(prisma, actor, async tx => {
    const companyId = actor.companyId;
    if (!await tx.companyTeam.findUnique({ where: { companyId_id: { companyId, id: teamId } } })) fail(404, 'Company team not found.');
    // Removal must also permit cleaning up a previously assigned, now-inactive member.
    const user = await tx.user.findFirst({ where: { companyId, username,
      ...(!remove ? { isActive: true, isCompanyVerified: true, emailVerified: true } : {}) }, select: { id: true } });
    if (!user) fail(404, 'No eligible member with that exact username was found in your company.');
    const scope = { companyId, teamId, userId: user.id };
    const where = { companyId_teamId_userId: scope };
    if (remove) {
      const result = await tx.teamAssignment.deleteMany({ where: scope });
      if (!result.count) fail(404, 'Team assignment not found.');
      return { username };
    }
    if (!await tx.teamAssignment.findUnique({ where }) && await tx.teamAssignment.count({ where: { companyId, teamId } }) >= 200) {
      fail(409, 'A team can have at most 200 assignments. Remove an assignment first.');
    }
    await tx.teamAssignment.upsert({ where, create: { ...scope, assignment }, update: { assignment } });
    return { username, assignment };
  });
}
module.exports = { listTeams, saveTeam, deleteTeam, assignMember };
