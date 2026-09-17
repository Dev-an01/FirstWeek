const express = require('express');
const axios = require('axios');
const { createHash } = require('node:crypto');
const rateLimit = require('express-rate-limit');
const { findProjectMembership } = require('../services/projectAccess');
const { profileOf } = require('../services/onboardingProfiles');
const { companyContext, companySources } = require('../services/companyContext');
const { listDocuments, searchDocuments } = require('../services/projectDocuments');
const { listResponsibilities } = require('../services/projectResponsibilities');
const store = require('../services/projectConversations');

// Mounted only after session, company, project-membership and mutation-origin checks.
module.exports = function conversationRoutes(prisma, managementWrite) {
  const router = express.Router({ mergeParams: true });
  async function rag(project, suffix, data) {
    const token = process.env.FIRSTWEEK_SERVICE_TOKEN || '';
    if (token.length < 32) throw Object.assign(new Error('Project knowledge is unavailable.'), { status: 503 });
    const base = process.env.FIRSTWEEK_RAG_URL || process.env.RAG_API_URL || 'http://rag-api:8000';
    const result = await axios({ method: data ? 'POST' : 'GET',
      url: `${base}/internal/firstweek/${encodeURIComponent(project.companyId)}/${encodeURIComponent(project.id)}${suffix}`,
      data, headers: { 'X-FirstWeek-Token': token }, timeout: 45000, maxRedirects: 0, maxContentLength: 2 * 1024 * 1024 });
    return result.data;
  }
  async function context(req) {
    const membership = await findProjectMembership(prisma, req.user, req.params.projectId);
    if (!membership) throw Object.assign(new Error('Project resource not found.'), { status: 404 });
    const project = membership.project;
    const onboardingProfile = profileOf(membership);
    const company = await companyContext(prisma, req.user);
    const documents = await listDocuments(prisma, req.user, project.id);
    const responsibilities = (await listResponsibilities(prisma, req.user, project.id)).map(r => ({
      id: r.id, name: r.name, description: r.description, status: r.status,
      owner: r.owner ? `${r.owner.firstName} ${r.owner.lastName} (@${r.owner.username})` : null,
      updatedAt: r.updatedAt.toISOString() }));
    const curated = project.hasCuratedKnowledge ? (await rag(project, '')).documents : [];
    if (!Array.isArray(curated)) throw new Error('Invalid knowledge metadata');
    const evidence = [project.name, project.knowledgeVersion, documents, curated, responsibilities];
    // Preserve existing conversations on upgrade until a member actually changes preferences.
    if (onboardingProfile.profileVersion > 0) evidence.push(onboardingProfile);
    if (company.hash) evidence.push(company.hash);
    const hash = createHash('sha256').update(JSON.stringify(evidence)).digest('hex');
    return { project, responsibilities, onboardingProfile, company,
      snapshot: { hash, version: project.knowledgeVersion, profileVersion: onboardingProfile.profileVersion } };
  }
  const handle = fn => async (req, res, next) => {
    try { res.json(await fn(req)); }
    catch (error) { if (error.status) return res.status(error.status).json({ error: error.message });
      return res.status(503).json({ error: 'Saved conversations are unavailable. Please try again.' }); }
  };
  router.get('/', handle(async req => ({ conversations: await store.listConversations(prisma, req.user, req.params.projectId, (await context(req)).snapshot) })));
  router.post('/', managementWrite, handle(async req => {
    if (!req.body || Object.keys(req.body).length) throw Object.assign(new Error('Send an empty JSON object.'), { status: 400 });
    return store.createConversation(prisma, req.user, req.params.projectId, (await context(req)).snapshot);
  }));
  router.get('/:conversationId', handle(async req => store.readConversation(prisma, req.user, req.params.projectId,
    req.params.conversationId, (await context(req)).snapshot)));
  router.delete('/:conversationId', managementWrite, handle(req => store.deleteConversation(prisma, req.user, req.params.projectId, req.params.conversationId)));
  router.post('/:conversationId/turns', managementWrite, rateLimit({ windowMs: 60000, max: 12,
    keyGenerator: req => req.user.id, standardHeaders: true, legacyHeaders: false,
    message: { error: 'Question limit reached. Try again in a minute.' } }), handle(async req => {
    const initial = await context(req);
    const reservation = await store.beginTurn(prisma, req.user, req.params.projectId, req.params.conversationId, initial.snapshot, req.body);
    if (reservation.completed) return reservation.completed;
    const row = reservation.conversation;
    try {
      const history = row.turns.slice(-3).flatMap(turn => [
        { role: 'user', content: turn.question }, { role: 'assistant', content: Array.from(turn.answer).slice(0, 2000).join('') }]);
      const recent = history.filter(m => m.role === 'user').slice(-2).map(m => m.content);
      const managedSources = await searchDocuments(prisma, req.user, req.params.projectId, [row.pendingQuestion, ...recent].join('\n').slice(0, 2000));
      const answer = await rag(initial.project, '/ask', { question: row.pendingQuestion, history,
        projectName: initial.project.name, hasCuratedKnowledge: initial.project.hasCuratedKnowledge,
        responsibilities: initial.responsibilities, managedSources, onboardingProfile: initial.onboardingProfile,
        companySources: companySources(initial.company, [row.pendingQuestion, ...recent].join('\n').slice(0, 2000)) });
      const current = await context(req);
      return await store.finishTurn(prisma, req.user, req.params.projectId, row, current.snapshot, answer);
    } catch (error) {
      await store.failTurn(prisma, req.user, req.params.projectId, row);
      throw error;
    }
  }));
  return router;
};
