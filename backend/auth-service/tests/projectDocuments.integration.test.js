const { test } = require('node:test');
const assert = require('node:assert/strict');
const { randomUUID } = require('node:crypto');

test('managed documents are project-scoped, durable, searchable and deleted with their chunks',
  { skip: process.env.FIRSTWEEK_TEST_DATABASE !== '1' }, async () => {
    process.env.DATABASE_URL = process.env.FIRSTWEEK_DATABASE_URL || 'postgresql://firstweek_local@127.0.0.1:5547/firstweek_demo';
    const { prisma } = require('../shared/lib/prisma');
    const { createProject, manageProject } = require('../services/projectAdministration');
    const { createDocument, listDocuments, readDocument, searchDocuments, deleteDocument, MAX_BYTES } = require('../services/projectDocuments');
    const companyId = `documents-${randomUUID()}`;
    try {
      await prisma.company.create({ data: { id: companyId, name: 'Document test', allowedDomains: [] } });
      const admin = await prisma.user.create({ data: { username: `${companyId}-admin`, firstName: 'Admin', lastName: 'Test',
        password: 'not-a-login-hash', companyId, role: 'COMPANY_ADMIN', isActive: true, isCompanyVerified: true, emailVerified: true } });
      const member = await prisma.user.create({ data: { username: `${companyId}-member`, firstName: 'Member', lastName: 'Test',
        password: 'not-a-login-hash', companyId, role: 'EMPLOYEE', isActive: true, isCompanyVerified: true, emailVerified: true } });
      const project = await createProject(prisma, admin, { name: 'Documents' });
      const other = await createProject(prisma, admin, { name: 'Other project' });
      await manageProject(prisma, admin, project.id, 'add', { username: member.username, role: 'MEMBER' });
      await assert.rejects(createDocument(prisma, member, project.id, { filename: 'denied.md', content: 'No.' }), { status: 403 });
      await assert.rejects(createDocument(prisma, admin, project.id, { filename: '../unsafe.md', content: 'No.' }), { status: 400 });
      await assert.rejects(createDocument(prisma, admin, project.id, { filename: 'large.txt', content: 'x'.repeat(MAX_BYTES + 1) }), { status: 400 });
      for (const content of ['binary\0data', '\ud800', '# title\ntext\ufffd']) {
        await assert.rejects(createDocument(prisma, admin, project.id, { filename: 'invalid.txt', content }), { status: 400 });
      }
      const unicode = 'a'.repeat(1399) + '😀 lighthouse ' + 'x'.repeat(1300);
      const emoji = await createDocument(prisma, admin, project.id, { filename: 'unicode.txt', content: unicode });
      assert.equal((await readDocument(prisma, member, project.id, emoji.id)).content, unicode);
      const unicodeChunks = await prisma.projectDocumentChunk.findMany({ where: { companyId, projectId: project.id, documentId: emoji.id } });
      assert.ok(unicodeChunks.every(chunk => !/\p{Surrogate}/u.test(chunk.content)));
      await deleteDocument(prisma, admin, project.id, emoji.id);
      const created = await createDocument(prisma, admin, project.id, { filename: 'release.md', title: 'Release guide',
        content: '# Release\nThe deployment lighthouse phrase proves managed retrieval.\n\n## Checks\nRun smoke checks before promotion.' });
      assert.equal((await listDocuments(prisma, member, project.id))[0].id, created.id);
      assert.match((await readDocument(prisma, member, project.id, created.id)).content, /lighthouse phrase/);
      assert.equal((await listDocuments(prisma, admin, other.id)).length, 0);
      await assert.rejects(readDocument(prisma, admin, other.id, created.id), { status: 404 });
      await assert.rejects(deleteDocument(prisma, member, project.id, created.id), { status: 403 });
      await assert.rejects(readDocument(prisma, { ...admin, companyId: 'wrong-company' }, project.id, created.id), { status: 404 });
      await assert.rejects(deleteDocument(prisma, { ...admin, companyId: 'wrong-company' }, project.id, created.id), { status: 404 });
      await assert.rejects(deleteDocument(prisma, admin, other.id, created.id), { code: 'P2025' });
      const hits = await searchDocuments(prisma, member, project.id, 'Where is the deployment lighthouse phrase?');
      assert.equal(hits[0].documentId, created.id); assert.match(hits[0].content, /lighthouse phrase/);
      await prisma.$disconnect();
      assert.equal((await listDocuments(prisma, member, project.id)).length, 1);
      await deleteDocument(prisma, admin, project.id, created.id);
      assert.equal((await listDocuments(prisma, member, project.id)).length, 0);
      assert.equal(await prisma.projectDocumentChunk.count({ where: { companyId, projectId: project.id } }), 0);
      assert.equal((await searchDocuments(prisma, member, project.id, 'lighthouse')).length, 0);
      await assert.rejects(readDocument(prisma, member, project.id, created.id), { status: 404 });
      await prisma.projectDocument.createMany({ data: Array.from({ length: 99 }, (_, i) => ({ companyId, projectId: project.id,
        id: `limit-${i}`, title: 'Limit fixture', filename: 'limit.txt', mediaType: 'text/plain', content: 'Limit', sha256: 'test', byteSize: 5 })) });
      const race = await Promise.allSettled([1, 2].map(i => createDocument(prisma, admin, project.id, { filename: `limit-${i}.txt`, content: 'Last available slot' })));
      assert.equal(race.filter(item => item.status === 'fulfilled').length, 1);
      assert.equal(race.find(item => item.status === 'rejected').reason.status, 409);
    } finally {
      await prisma.project.deleteMany({ where: { companyId } });
      await prisma.user.deleteMany({ where: { companyId } });
      await prisma.company.deleteMany({ where: { id: companyId } });
      await prisma.$disconnect();
    }
  });
