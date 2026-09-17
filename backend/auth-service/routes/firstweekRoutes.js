const express = require('express');
const axios = require('axios');
const rateLimit = require('express-rate-limit');
const { prisma } = require('../shared/lib/prisma');
const { requireAuth } = require('../middleware/authMiddleware');
const { findProjectMembership } = require('../services/projectAccess');
const { readProfile, saveProfile } = require('../services/onboardingProfiles');
const { listTeams, saveTeam, deleteTeam, assignMember } = require('../services/companyTeams');
const { companyContext, companySources } = require('../services/companyContext');
const { createProject, manageProject } = require('../services/projectAdministration');
const { listResponsibilities, saveResponsibility, deleteResponsibility } = require('../services/projectResponsibilities');
const { listDocuments, readDocument, createDocument, deleteDocument, searchDocuments } = require('../services/projectDocuments');
const { readPath, saveStep, removeStep, reorderSteps, completeStep } = require('../services/readingPaths');

const router = express.Router();
const responsibilityPayload = items => items.slice(0, 100).map(item => ({ id: item.id, name: item.name,
  description: item.description, status: item.status,
  owner: item.owner ? `${item.owner.firstName} ${item.owner.lastName} (@${item.owner.username})` : null,
  ownerUserId: item.ownerUserId, updatedAt: item.updatedAt.toISOString() }));
router.use(requireAuth);
router.use((req, res, next) => {
  res.set('Cache-Control', 'no-store');
  if (!req.user.companyId || !req.user.isCompanyVerified || !req.user.isActive) {
    return res.status(403).json({ error: 'Verified company membership is required.' });
  }
  return next();
});

router.get('/projects', async (req, res) => {
  const memberships = await prisma.projectMember.findMany({
    where: { userId: req.user.id, companyId: req.user.companyId, project: { isActive: true } },
    include: { project: true },
    orderBy: { project: { name: 'asc' } },
  });
  return res.json({ canCreate: req.user.role === 'COMPANY_ADMIN', projects: memberships.map(({ project, role }) => ({ ...project, membershipRole: role })) });
});

function managementWrite(req, res, next) {
  const expectedOrigin = process.env.FIRSTWEEK_ORIGIN || `${req.protocol}://${req.get('host')}`;
  if (req.get('origin') !== expectedOrigin || req.get('sec-fetch-site') === 'cross-site') {
    return res.status(403).json({ error: 'Open this workspace in its original browser tab and try again.' });
  }
  if (!req.is('application/json')) return res.status(415).json({ error: 'Send a JSON request.' });
  return next();
}
const mutation = (handler) => async (req, res, next) => {
  try { return res.status(req.method === 'POST' ? 201 : 200).json(await handler(req)); }
  catch (error) {
    if (error.status) return res.status(error.status).json({ error: error.message });
    if (error.code === 'P2002') return res.status(409).json({ error: 'This project membership already exists.' });
    if (error.code === 'P2025') return res.status(404).json({ error: 'Project resource not found.' });
    return next(error);
  }
};
router.post('/projects', managementWrite, mutation(req => createProject(prisma, req.user, req.body)));
router.get('/company/teams', mutation(req => listTeams(prisma, req.user)));
router.post('/company/teams', managementWrite, mutation(req => saveTeam(prisma, req.user, req.body)));
router.patch('/company/teams/:teamId', managementWrite, mutation(req => saveTeam(prisma, req.user, req.body, req.params.teamId)));
router.delete('/company/teams/:teamId', managementWrite, mutation(req => deleteTeam(prisma, req.user, req.params.teamId, req.body)));
router.put('/company/teams/:teamId/assignments', managementWrite, mutation(req => assignMember(prisma, req.user, req.params.teamId, req.body)));
router.delete('/company/teams/:teamId/assignments', managementWrite, mutation(req => assignMember(prisma, req.user, req.params.teamId, req.body, true)));

router.use('/projects/:projectId', async (req, res, next) => {
  const membership = await findProjectMembership(prisma, req.user, req.params.projectId);
  if (!membership) return res.status(404).json({ error: 'Project resource not found.' });
  req.firstweekProject = membership.project;
  req.firstweekMembershipRole = membership.role;
  return next();
});

router.patch('/projects/:projectId', managementWrite, mutation(req =>
  manageProject(prisma, req.user, req.params.projectId, 'settings', req.body)));
router.use('/projects/:projectId/conversations', require('./conversationRoutes')(prisma, managementWrite));
router.get('/projects/:projectId/onboarding-profile', mutation(req => readProfile(prisma, req.user, req.params.projectId)));
router.put('/projects/:projectId/onboarding-profile', managementWrite, mutation(req => saveProfile(prisma, req.user, req.params.projectId, req.body)));
router.get('/projects/:projectId/reading-path', mutation(req => readPath(prisma, req.user, req.params.projectId)));
router.post('/projects/:projectId/reading-path', managementWrite, mutation(req => saveStep(prisma, req.user, req.params.projectId, req.body)));
router.patch('/projects/:projectId/reading-path/:stepId', managementWrite, mutation(req => saveStep(prisma, req.user, req.params.projectId, req.body, req.params.stepId)));
router.delete('/projects/:projectId/reading-path/:stepId', managementWrite, mutation(req => removeStep(prisma, req.user, req.params.projectId, req.params.stepId)));
router.put('/projects/:projectId/reading-path/order', managementWrite, mutation(req => reorderSteps(prisma, req.user, req.params.projectId, req.body)));
router.put('/projects/:projectId/reading-path/:stepId/completion', managementWrite, mutation(req => completeStep(prisma, req.user, req.params.projectId, req.params.stepId, req.body)));
router.post('/projects/:projectId/members', managementWrite, mutation(req =>
  manageProject(prisma, req.user, req.params.projectId, 'add', req.body)));
router.patch('/projects/:projectId/members/:userId', managementWrite, mutation(req =>
  manageProject(prisma, req.user, req.params.projectId, 'role', req.body, req.params.userId)));
router.delete('/projects/:projectId/members/:userId', managementWrite, mutation(req =>
  manageProject(prisma, req.user, req.params.projectId, 'remove', req.body, req.params.userId)));
router.get('/projects/:projectId/responsibilities', async (req, res, next) => {
  try { return res.json({ responsibilities: await listResponsibilities(prisma, req.user, req.params.projectId) }); }
  catch (error) { return error.status ? res.status(error.status).json({ error: error.message }) : next(error); }
});
router.post('/projects/:projectId/responsibilities', managementWrite, mutation(req =>
  saveResponsibility(prisma, req.user, req.params.projectId, req.body)));
router.patch('/projects/:projectId/responsibilities/:responsibilityId', managementWrite, mutation(req =>
  saveResponsibility(prisma, req.user, req.params.projectId, req.body, req.params.responsibilityId)));
router.delete('/projects/:projectId/responsibilities/:responsibilityId', managementWrite, mutation(req =>
  deleteResponsibility(prisma, req.user, req.params.projectId, req.params.responsibilityId)));

async function forward(req, res, suffix, data, transform = value => value, documentsSnapshot, companySnapshot) {
  const token = process.env.FIRSTWEEK_SERVICE_TOKEN || '';
  if (token.length < 32) return res.status(503).json({ error: 'Project knowledge is not configured yet.' });
  const project = req.firstweekProject;
  const base = process.env.FIRSTWEEK_RAG_URL || process.env.RAG_API_URL || 'http://rag-api:8000';
  const url = `${base}/internal/firstweek/${encodeURIComponent(project.companyId)}/${encodeURIComponent(project.id)}${suffix}`;
  try {
    const result = await axios({ method: data ? 'POST' : 'GET', url, data,
      headers: { 'X-FirstWeek-Token': token }, timeout: 45000, maxRedirects: 0,
      maxContentLength: 2 * 1024 * 1024 });
    // Removal during a slow model call must also revoke the pending response.
    if (!await findProjectMembership(prisma, req.user, project.id)) {
      return res.status(404).json({ error: 'Project resource not found.' });
    }
    if (data?.responsibilities) {
      const current = await listResponsibilities(prisma, req.user, project.id);
      if (JSON.stringify(responsibilityPayload(current)) !== JSON.stringify(data.responsibilities)) {
        return res.status(409).json({ error: 'Project responsibilities changed while answering. Please ask again.' });
      }
    }
    if (data?.onboardingProfile && JSON.stringify(await readProfile(prisma, req.user, project.id)) !== JSON.stringify(data.onboardingProfile)) {
      return res.status(409).json({ error: 'Your onboarding preferences changed while answering. Please ask again.' });
    }
    if (documentsSnapshot && JSON.stringify(await listDocuments(prisma, req.user, project.id)) !== documentsSnapshot) {
      return res.status(409).json({ error: 'Project documents changed while loading. Please try again.' });
    }
    if (companySnapshot !== undefined && (await companyContext(prisma, req.user)).hash !== companySnapshot) {
      return res.status(409).json({ error: 'Company context changed while answering. Please ask again.' });
    }
    return res.json(transform(suffix === '' ? { ...result.data, name: project.name, summary: project.description,
      membershipRole: req.firstweekMembershipRole } : result.data));
  } catch (error) {
    if (error.response?.status === 404) return res.status(404).json({ error: 'Project knowledge has not been indexed yet.' });
    return res.status(503).json({ error: 'Project knowledge is unavailable. Please try again shortly.' });
  }
}

router.get('/projects/:projectId/members', async (req, res) => {
  const members = await prisma.projectMember.findMany({
    where: { companyId: req.firstweekProject.companyId, projectId: req.firstweekProject.id,
      user: { isActive: true, isCompanyVerified: true } },
    select: { userId: true, role: true, user: { select: { username: true, firstName: true, lastName: true, title: true } } },
  });
  if (!await findProjectMembership(prisma, req.user, req.firstweekProject.id)) {
    return res.status(404).json({ error: 'Project resource not found.' });
  }
  return res.json({ members: members.map(({ user, ...membership }) => ({ ...membership, ...user })) });
});

router.get('/projects/:projectId', async (req, res, next) => {
  const project = req.firstweekProject;
  try {
    const managed = await listDocuments(prisma, req.user, project.id);
    if (project.hasCuratedKnowledge === false) return res.json({ id: project.id, name: project.name,
    summary: project.description, membershipRole: req.firstweekMembershipRole,
    stack: [], documents: managed, architecture: null, knowledgeStatus: managed.length ? 'managed' : 'empty' });
    return forward(req, res, '', undefined, value => ({ ...value, documents: [...(value.documents || []), ...managed] }), JSON.stringify(managed));
  } catch (error) { return next(error); }
});
router.post('/projects/:projectId/documents', managementWrite, mutation(req =>
  createDocument(prisma, req.user, req.params.projectId, req.body)));
router.get('/projects/:projectId/documents/:documentId', async (req, res, next) => {
  if (/^m-[0-9a-f-]{36}$/.test(req.params.documentId)) {
    try { return res.json(await readDocument(prisma, req.user, req.params.projectId, req.params.documentId)); }
    catch (error) { return error.status ? res.status(error.status).json({ error: error.message }) : next(error); }
  }
  if (!/^[a-f0-9]{32}$/.test(req.params.documentId)) return res.status(404).json({ error: 'Project resource not found.' });
  return forward(req, res, `/documents/${req.params.documentId}`);
});
router.delete('/projects/:projectId/documents/:documentId', managementWrite, mutation(req =>
  deleteDocument(prisma, req.user, req.params.projectId, req.params.documentId)));
router.post('/projects/:projectId/ask', rateLimit({
  windowMs: 60 * 1000, max: 12, keyGenerator: (req) => req.user.id,
  standardHeaders: true, legacyHeaders: false,
  message: { error: 'Question limit reached. Try again in a minute.' },
}), async (req, res, next) => {
  const question = req.body?.question;
  if (typeof question !== 'string' || !question.trim() || question.length > 2000) {
    return res.status(400).json({ error: 'Enter a question between 1 and 2000 characters.' });
  }
  const history = req.body?.history ?? [];
  if (!Array.isArray(history) || history.length > 6 || history.some((message) =>
    !message || !['user', 'assistant'].includes(message.role) ||
    typeof message.content !== 'string' || !message.content.trim() || message.content.length > 4000)) {
    return res.status(400).json({ error: 'Conversation context is invalid. Start a new conversation.' });
  }
  try {
    const responsibilities = await listResponsibilities(prisma, req.user, req.params.projectId);
    const onboardingProfile = await readProfile(prisma, req.user, req.params.projectId);
    const company = await companyContext(prisma, req.user);
    const documentsSnapshot = JSON.stringify(await listDocuments(prisma, req.user, req.params.projectId));
    const recent = history.filter(message => message.role === 'user').slice(-2).map(message => message.content);
    const managedSources = await searchDocuments(prisma, req.user, req.params.projectId, [question, ...recent].join('\n').slice(0, 2000));
    const maintainedCompanySources = companySources(company, [question, ...recent].join('\n').slice(0, 2000));
    if (req.firstweekProject.hasCuratedKnowledge === false && !responsibilities.length && !managedSources.length && !maintainedCompanySources.length) return res.json({
      answer: 'No matching evidence was found. Try a more specific question or ask a maintainer to add a source.', sources: [], mode: 'no-evidence', retrieval: 'none' });
    return forward(req, res, '/ask', { question: question.trim(), projectName: req.firstweekProject.name,
      hasCuratedKnowledge: req.firstweekProject.hasCuratedKnowledge,
      responsibilities: responsibilityPayload(responsibilities), managedSources, onboardingProfile, companySources: maintainedCompanySources,
      history: history.map(({ role, content }) => ({ role, content })) }, undefined, documentsSnapshot, company.hash);
  } catch (error) { return next(error); }
});
router.use((error, req, res, next) => {
  if (res.headersSent) return next(error);
  return res.status(503).json({ error: 'Project workspace is unavailable. Please try again shortly.' });
});
module.exports = router;
