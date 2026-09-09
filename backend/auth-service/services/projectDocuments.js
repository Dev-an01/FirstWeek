const { createHash, randomUUID } = require('node:crypto');
const { findProjectMembership } = require('./projectAccess');

const MAX_BYTES = 256 * 1024;
const TYPES = { '.md': 'text/markdown', '.txt': 'text/plain' };
const STOP = new Set('a an and are as at be by for from how in is it of on or that the this to was what when where which who why with'.split(' '));
function fail(status, message) { throw Object.assign(new Error(message), { status }); }
function scope(actor, projectId) { return { companyId: actor.companyId, projectId }; }
function view(row, content = false) { return { id: row.id, title: row.title, filename: row.filename,
  mediaType: row.mediaType, sha256: row.sha256, byteSize: row.byteSize, snapshot_at: row.updatedAt,
  managed: true, ...(content ? { content: row.content, evidence: [] } : {}) }; }
function payload(body) {
  if (!body || Array.isArray(body) || typeof body !== 'object' ||
      Object.keys(body).some(k => !['filename', 'title', 'content'].includes(k)) ||
      typeof body.filename !== 'string' || typeof body.content !== 'string' ||
      (body.title !== undefined && typeof body.title !== 'string')) fail(400, 'Document fields are invalid.');
  const filename = body.filename.trim();
  const extension = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  const bytes = Buffer.byteLength(body.content, 'utf8');
  if (!/^[^/\\\0]{1,160}$/.test(filename) || !TYPES[extension]) fail(400, 'Upload a .md or .txt file with a safe filename.');
  if (!body.content.trim() || bytes > MAX_BYTES) fail(400, 'Document text must contain 1–262144 UTF-8 bytes.');
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffd\p{Surrogate}]/u.test(body.content)) fail(400, 'Upload valid UTF-8 text without binary control characters.');
  const title = (body.title ?? filename.replace(/\.[^.]+$/, '')).trim();
  if (!title || title.length > 160) fail(400, 'Document title must contain 1–160 characters.');
  if (/[\u0000-\u001f\p{Surrogate}]/u.test(filename + title)) fail(400, 'Filename and title must contain valid text.');
  return { filename, title, content: body.content.replace(/\r\n/g, '\n'), mediaType: TYPES[extension], byteSize: bytes };
}
function chunks(content) {
  const values = []; let heading = 'Overview'; let text = '';
  const flush = () => { const clean = Array.from(text.trim()); for (let i = 0; i < clean.length; i += 1200) {
    const part = clean.slice(i, i + 1400).join(''); if (part) values.push({ heading, content: part }); } text = ''; };
  for (const line of content.split('\n')) { const match = /^#{1,3}\s+(.+)$/.exec(line);
    if (match) { flush(); heading = Array.from(match[1].trim()).slice(0, 100).join('') || 'Overview'; }
    text += `${line}\n`; }
  flush();
  if (values.length > 240) fail(400, 'Document has too many sections; use at most 240 text chunks.');
  return values.length ? values : [{ heading: 'Overview', content: content.trim() }];
}
async function requireMember(prisma, actor, projectId, maintainer = false) {
  const member = await findProjectMembership(prisma, actor, projectId);
  if (!member) fail(404, 'Project resource not found.');
  if (maintainer && member.role !== 'MAINTAINER') fail(403, 'Only project maintainers can manage documents.');
  return member;
}
async function listDocuments(prisma, actor, projectId) {
  await requireMember(prisma, actor, projectId);
  const rows = await prisma.projectDocument.findMany({ where: scope(actor, projectId),
    select: { id: true, title: true, filename: true, mediaType: true, sha256: true, byteSize: true, updatedAt: true },
    orderBy: [{ createdAt: 'asc' }, { id: 'asc' }] });
  if (!await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  return rows.map(row => view(row));
}
async function readDocument(prisma, actor, projectId, id) {
  await requireMember(prisma, actor, projectId);
  const row = await prisma.projectDocument.findUnique({ where: { companyId_projectId_id: { ...scope(actor, projectId), id } } });
  if (!row || !await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  return view(row, true);
}
async function createDocument(prisma, actor, projectId, body) {
  const data = payload(body);
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await requireMember(tx, actor, projectId, true);
    if (await tx.projectDocument.count({ where: scope(actor, projectId) }) >= 100) fail(409, 'This project has reached its 100-document limit.');
    const id = `m-${randomUUID()}`; const parts = chunks(data.content);
    const row = await tx.projectDocument.create({ data: { ...scope(actor, projectId), id, ...data,
      sha256: createHash('sha256').update(data.content).digest('hex'),
      chunks: { create: parts.map((part, position) => ({ position, ...part })) } } });
    return view(row);
  });
}
async function deleteDocument(prisma, actor, projectId, id) {
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    await requireMember(tx, actor, projectId, true);
    await tx.projectDocument.delete({ where: { companyId_projectId_id: { ...scope(actor, projectId), id } } });
    return { id };
  });
}
async function searchDocuments(prisma, actor, projectId, query, limit = 8) {
  await requireMember(prisma, actor, projectId);
  const terms = [...new Set((query.toLowerCase().match(/[\p{L}\p{N}_-]+/gu) || []).filter(t => t.length > 1 && !STOP.has(t)).slice(0, 32))];
  if (!terms.length) return [];
  // ponytail: bounded lexical scan (100 documents, 256 KiB each); use PostgreSQL FTS when corpus size grows.
  const rows = await prisma.projectDocumentChunk.findMany({ where: scope(actor, projectId), include: { document: { select: { updatedAt: true } } } });
  const ranked = rows.map(row => ({ row, score: terms.reduce((n, term) => n + ((`${row.heading}\n${row.content}`.toLowerCase().match(new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length), 0) }))
    .filter(x => x.score).sort((a, b) => b.score - a.score || a.row.position - b.row.position).slice(0, limit);
  if (!await findProjectMembership(prisma, actor, projectId)) fail(404, 'Project resource not found.');
  return ranked.map(({ row, score }) => ({ id: `${row.documentId}:${row.position}`, kind: 'document', documentId: row.documentId,
    heading: row.heading, content: row.content, score, projectId, updatedAt: row.document.updatedAt.toISOString() }));
}
module.exports = { MAX_BYTES, listDocuments, readDocument, createDocument, deleteDocument, searchDocuments };
