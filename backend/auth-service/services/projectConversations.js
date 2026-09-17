const { randomUUID } = require('node:crypto');
const { findProjectMembership } = require('./projectAccess');
const cleared = { turns: [], title: 'Conversation reset after source changes', pendingId: null, pendingQuestion: null, pendingAt: null };
const scope = (actor, projectId) => ({ companyId: actor.companyId, projectId, userId: actor.id });
const key = (actor, projectId, id) => ({ companyId_projectId_userId_id: { ...scope(actor, projectId), id } });
function fail(status, message) { throw Object.assign(new Error(message), { status }); }
async function locked(prisma, actor, projectId, operation) {
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    if (!await findProjectMembership(tx, actor, projectId)) fail(404, 'Project resource not found.');
    return operation(tx);
  });
}
async function refresh(tx, actor, projectId, hash) {
  await assertSnapshot(tx, actor, projectId, hash);
  await tx.projectConversation.updateMany({ where: { ...scope(actor, projectId), knowledgeHash: { not: hash.hash } },
    data: { ...cleared, knowledgeHash: hash.hash, version: { increment: 1 } } });
  await tx.projectConversation.updateMany({ where: { ...scope(actor, projectId), pendingAt: { lt: new Date(Date.now() - 60000) } },
    data: { pendingId: null, pendingAt: null, version: { increment: 1 } } });
}
async function assertSnapshot(tx, actor, projectId, snapshot) {
  const project = await tx.project.findUnique({ where: { companyId_id: { companyId: actor.companyId, id: projectId } } });
  if (project.knowledgeVersion !== snapshot.version) fail(409, 'Project sources changed. Try again.');
  if (snapshot.profileVersion !== undefined) {
    const member = await findProjectMembership(tx, actor, projectId);
    if (!member || member.profileVersion !== snapshot.profileVersion) fail(409, 'Your onboarding preferences changed. Try again.');
  }
}
async function listConversations(prisma, actor, projectId, hash) {
  return locked(prisma, actor, projectId, async tx => {
    await refresh(tx, actor, projectId, hash);
    return tx.projectConversation.findMany({ where: scope(actor, projectId), orderBy: { updatedAt: 'desc' },
      select: { id: true, title: true, updatedAt: true } });
  });
}
async function createConversation(prisma, actor, projectId, hash) {
  return locked(prisma, actor, projectId, async tx => {
    await assertSnapshot(tx, actor, projectId, hash);
    if (await tx.projectConversation.count({ where: scope(actor, projectId) }) >= 50) fail(409, 'Delete an old conversation before creating another (50 maximum).');
    return tx.projectConversation.create({ data: { ...scope(actor, projectId), id: randomUUID(), knowledgeHash: hash.hash } });
  });
}
async function readConversation(prisma, actor, projectId, id, hash) {
  return locked(prisma, actor, projectId, async tx => {
    await refresh(tx, actor, projectId, hash);
    const row = await tx.projectConversation.findUnique({ where: key(actor, projectId, id) });
    if (!row) fail(404, 'Conversation not found.');
    return row;
  });
}
async function deleteConversation(prisma, actor, projectId, id) {
  return locked(prisma, actor, projectId, async tx => {
    const result = await tx.projectConversation.deleteMany({ where: { ...scope(actor, projectId), id } });
    if (!result.count) fail(404, 'Conversation not found.');
    return { id };
  });
}
async function beginTurn(prisma, actor, projectId, id, hash, body) {
  if (!body || typeof body !== 'object' || Object.keys(body).some(k => !['question', 'requestId'].includes(k)) ||
      typeof body.question !== 'string' || !body.question.trim() || body.question.length > 2000 ||
      /[\u0000\p{Surrogate}]/u.test(body.question) || typeof body.requestId !== 'string' ||
      !/^[a-f0-9-]{36}$/.test(body.requestId)) fail(400, 'A question and valid request ID are required.');
  return locked(prisma, actor, projectId, async tx => {
    await refresh(tx, actor, projectId, hash);
    const row = await tx.projectConversation.findUnique({ where: key(actor, projectId, id) });
    if (!row) fail(404, 'Conversation not found.');
    const question = body.question.trim();
    const previous = row.turns.find(turn => turn.requestId === body.requestId);
    if (previous) {
      if (previous.question !== question) fail(409, 'This request ID belongs to another question.');
      return { completed: row };
    }
    if (row.pendingId) fail(409, 'An answer is already in progress. Reload this conversation shortly.');
    if (row.turns.length >= 20) fail(409, 'Start a new conversation after 20 turns.');
    return { conversation: await tx.projectConversation.update({ where: key(actor, projectId, id),
      data: { pendingId: body.requestId, pendingQuestion: question, pendingAt: new Date(), version: { increment: 1 } } }) };
  });
}
async function finishTurn(prisma, actor, projectId, reserved, currentHash, answer) {
  return locked(prisma, actor, projectId, async tx => {
    await assertSnapshot(tx, actor, projectId, currentHash);
    const row = await tx.projectConversation.findUnique({ where: key(actor, projectId, reserved.id) });
    if (!row || row.version !== reserved.version || row.pendingId !== reserved.pendingId) fail(409, 'Conversation changed. Reload before asking again.');
    if (row.knowledgeHash !== currentHash.hash) fail(409, 'Project sources changed. Reload before asking again.');
    if (!answer || typeof answer.answer !== 'string' || !Array.isArray(answer.sources) ||
        Buffer.byteLength(JSON.stringify(answer)) > 300000) fail(503, 'The answer could not be saved. Try again.');
    return tx.projectConversation.update({ where: key(actor, projectId, row.id), data: {
      turns: [...row.turns, { requestId: row.pendingId, question: row.pendingQuestion, answer: answer.answer,
        sources: answer.sources, mode: answer.mode || 'generated' }],
      title: row.turns.length ? row.title : Array.from(row.pendingQuestion).slice(0, 70).join(''),
      pendingId: null, pendingAt: null, pendingQuestion: null } });
  });
}
async function failTurn(prisma, actor, projectId, row) {
  return prisma.projectConversation.updateMany({ where: { ...scope(actor, projectId), id: row.id, version: row.version },
    data: { pendingId: null, pendingAt: null } });
}
module.exports = { cleared, listConversations, createConversation, readConversation, deleteConversation, beginTurn, finishTurn, failTurn };
