const express = require('express');
const axios = require('axios');
const rateLimit = require('express-rate-limit');
const { prisma } = require('../shared/lib/prisma');
const { requireAuth } = require('../middleware/authMiddleware');
const { findProjectMembership } = require('../services/projectAccess');

const router = express.Router();
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
  return res.json({ projects: memberships.map(({ project, role }) => ({ ...project, membershipRole: role })) });
});

router.use('/projects/:projectId', async (req, res, next) => {
  const membership = await findProjectMembership(prisma, req.user, req.params.projectId);
  if (!membership) return res.status(404).json({ error: 'Project resource not found.' });
  req.firstweekProject = membership.project;
  return next();
});

async function forward(req, res, suffix, data) {
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
    return res.json(result.data);
  } catch (error) {
    if (error.response?.status === 404) return res.status(404).json({ error: 'Project knowledge has not been indexed yet.' });
    return res.status(503).json({ error: 'Project knowledge is unavailable. Please try again shortly.' });
  }
}

router.get('/projects/:projectId/members', async (req, res) => {
  const members = await prisma.projectMember.findMany({
    where: { companyId: req.firstweekProject.companyId, projectId: req.firstweekProject.id,
      user: { isActive: true, isCompanyVerified: true } },
    select: { userId: true, role: true, user: { select: { firstName: true, lastName: true, title: true } } },
  });
  if (!await findProjectMembership(prisma, req.user, req.firstweekProject.id)) {
    return res.status(404).json({ error: 'Project resource not found.' });
  }
  return res.json({ members: members.map(({ user, ...membership }) => ({ ...membership, ...user })) });
});

router.get('/projects/:projectId', (req, res) => forward(req, res, ''));
router.get('/projects/:projectId/documents/:documentId', (req, res) => {
  if (!/^[a-f0-9]{32}$/.test(req.params.documentId)) return res.status(404).json({ error: 'Project resource not found.' });
  return forward(req, res, `/documents/${req.params.documentId}`);
});
router.post('/projects/:projectId/ask', rateLimit({
  windowMs: 60 * 1000, max: 12, keyGenerator: (req) => req.user.id,
  standardHeaders: true, legacyHeaders: false,
  message: { error: 'Question limit reached. Try again in a minute.' },
}), (req, res) => {
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
  return forward(req, res, '/ask', { question: question.trim(),
    history: history.map(({ role, content }) => ({ role, content })) });
});
router.use((error, req, res, next) => {
  if (res.headersSent) return next(error);
  return res.status(503).json({ error: 'Project workspace is unavailable. Please try again shortly.' });
});
module.exports = router;
