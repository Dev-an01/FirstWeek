const { randomUUID } = require('node:crypto');
const { findProjectMembership } = require('./projectAccess');

function fail(status, message) { throw Object.assign(new Error(message), { status }); }
const scope = (actor, projectId) => ({ companyId: actor.companyId, projectId });
const text = (value, max, label, optional = false) => {
  if (typeof value !== 'string' || value.length > max || (!optional && !value.trim())) fail(400, `${label} must contain ${optional ? '0' : '1'}–${max} characters.`);
  return value.trim();
};
async function member(prisma, actor, projectId, maintainer = false) {
  const value = await findProjectMembership(prisma, actor, projectId);
  if (!value) fail(404, 'Project resource not found.');
  if (maintainer && value.role !== 'MAINTAINER') fail(403, 'Only project maintainers can manage the reading path.');
  return value;
}
function stepView(row, completed = false) { return { id: row.id, title: row.title, description: row.description, documentId: row.documentId,
  focus: row.focus, experience: row.experience, position: row.position, revision: row.revision, completed }; }
function matches(row, profile) { return (!row.focus || row.focus === profile.onboardingRole) && (!row.experience || row.experience === profile.onboardingExperience); }
async function readPath(prisma, actor, projectId) {
  const current = await member(prisma, actor, projectId);
  const rows = await prisma.projectReadingStep.findMany({ where: scope(actor, projectId), orderBy: { position: 'asc' } });
  const progress = await prisma.projectReadingProgress.findMany({ where: { ...scope(actor, projectId), userId: actor.id }, select: { stepId: true, stepRevision: true } });
  if (!await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  const completed = new Map(progress.map(row => [row.stepId, row.stepRevision]));
  const profile = { onboardingRole: current.onboardingRole, onboardingExperience: current.onboardingExperience };
  const steps = rows.filter(row => matches(row, profile)).map(row => stepView(row, completed.get(row.id) === row.revision));
  // Management needs every step, but a maintainer's personal progress remains profile-filtered.
  const managedSteps = current.role === 'MAINTAINER' ? rows.map(row => stepView(row, completed.get(row.id) === row.revision)) : undefined;
  return { canManage: current.role === 'MAINTAINER', steps, ...(managedSteps ? { managedSteps } : {}), completed: steps.filter(step => step.completed).length, total: steps.length };
}
function input(body) {
  if (!body || Array.isArray(body) || typeof body !== 'object' || Object.keys(body).some(key => !['title', 'description', 'documentId', 'focus', 'experience'].includes(key))) fail(400, 'Reading-step fields are invalid.');
  const focus = body.focus ?? null, experience = body.experience ?? null;
  if (![null, 'ENGINEERING', 'PRODUCT', 'DESIGN', 'OPERATIONS'].includes(focus) || ![null, 'NEW', 'EXPERIENCED'].includes(experience)) fail(400, 'Reading-step filters are invalid.');
  return { title: text(body.title, 120, 'Title'), description: text(body.description ?? '', 800, 'Description', true), documentId: text(body.documentId, 100, 'Document ID'), focus, experience };
}
async function saveStep(prisma, actor, projectId, body, id) {
  const data = input(body);
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await member(tx, actor, projectId, true);
    const document = await tx.projectDocument.findUnique({ where: { companyId_projectId_id: { ...scope(actor, projectId), id: data.documentId } } });
    if (!document) fail(404, 'Choose an existing managed project source.');
    const base = scope(actor, projectId);
    if (!id) {
      const count = await tx.projectReadingStep.count({ where: base });
      if (count >= 50) fail(409, 'This project has reached its 50-step reading-path limit.');
      // Source deletion cascades its steps. Append after the greatest surviving
      // position rather than count so a resulting gap never collides with UNIQUE.
      const last = await tx.projectReadingStep.aggregate({ where: base, _max: { position: true } });
      const position = (last._max.position ?? -1) + 1;
      const row = await tx.projectReadingStep.create({ data: { ...base, ...data, id: `r-${randomUUID()}`, position } });
      return stepView(row);
    }
    const existing = await tx.projectReadingStep.findUnique({ where: { companyId_projectId_id: { ...base, id } } });
    if (!existing) fail(404, 'Reading step not found.');
    const changed = ['title', 'description', 'documentId', 'focus', 'experience'].some(key => existing[key] !== data[key]);
    const row = await tx.projectReadingStep.update({ where: { companyId_projectId_id: { ...base, id } }, data: { ...data, ...(changed ? { revision: { increment: 1 } } : {}) } });
    return stepView(row);
  });
}
async function removeStep(prisma, actor, projectId, id) {
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await member(tx, actor, projectId, true);
    const base = scope(actor, projectId);
    await tx.projectReadingStep.delete({ where: { companyId_projectId_id: { ...base, id } } });
    return { id };
  });
}
async function reorderSteps(prisma, actor, projectId, body) {
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).length !== 1 || !Array.isArray(body.stepIds) ||
      body.stepIds.length > 50 || body.stepIds.some(id => typeof id !== 'string' || !/^r-[0-9a-f-]{36}$/.test(id)) || new Set(body.stepIds).size !== body.stepIds.length) {
    fail(400, 'Reading-step order is invalid.');
  }
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await member(tx, actor, projectId, true);
    const base = scope(actor, projectId);
    const rows = await tx.projectReadingStep.findMany({ where: base, select: { id: true } });
    if (rows.length !== body.stepIds.length || rows.some(row => !body.stepIds.includes(row.id))) fail(409, 'Reload the reading path before reordering it.');
    // Move through an unused negative range first so PostgreSQL never observes a
    // transient duplicate under the composite unique position constraint.
    for (const [index, id] of body.stepIds.entries()) await tx.projectReadingStep.update({ where: { companyId_projectId_id: { ...base, id } }, data: { position: -index - 1 } });
    for (const [position, id] of body.stepIds.entries()) await tx.projectReadingStep.update({ where: { companyId_projectId_id: { ...base, id } }, data: { position } });
    return { stepIds: body.stepIds };
  });
}
async function completeStep(prisma, actor, projectId, id, body) {
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).length !== 1 || body.revision === undefined || !Number.isInteger(body.revision) || body.revision < 0) fail(400, 'Reading-step completion is invalid.');
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await member(tx, actor, projectId);
    const step = await tx.projectReadingStep.findUnique({ where: { companyId_projectId_id: { ...scope(actor, projectId), id } } });
    if (!step || step.revision !== body.revision) fail(409, 'This reading step changed. Reload it before marking it complete.');
    await tx.projectReadingProgress.upsert({ where: { companyId_projectId_stepId_userId: { ...scope(actor, projectId), stepId: id, userId: actor.id } },
      create: { ...scope(actor, projectId), stepId: id, userId: actor.id, stepRevision: step.revision }, update: { stepRevision: step.revision, completedAt: new Date() } });
    return { id, revision: step.revision, completed: true };
  });
}
module.exports = { readPath, saveStep, removeStep, reorderSteps, completeStep };
