import { useAuthStore } from '../store/authStore';

const base = import.meta.env.VITE_FIRSTWEEK_API_URL || '/api/firstweek';
async function request(path, { signal, question, history = [], method = 'GET', data } = {}) {
  if (question !== undefined) { method = 'POST'; data = { question, history }; }
  const response = await fetch(`${base}${path}`, {
    method,
    credentials: 'include',
    cache: 'no-store',
    signal,
    headers: { 'Content-Type': 'application/json' },
    ...(data === undefined ? {} : { body: JSON.stringify(data) }),
  });
  if (response.status === 401) {
    useAuthStore.setState({ user: null, isAuthenticated: false });
    throw new Error('Your session expired. Sign in again.');
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error('The workspace could not be reached. Please try again.');
  }
  if (!response.ok)
    throw new Error(
      body.error || 'The workspace could not be reached. Please try again.'
    );
  return body;
}
const prefix = (id) => `/projects/${encodeURIComponent(id)}`;
export const firstweekApi = {
  companyTeams: signal => request('/company/teams', { signal }),
  createCompanyTeam: data => request('/company/teams', { method: 'POST', data }),
  saveCompanyTeam: (id, data) => request(`/company/teams/${encodeURIComponent(id)}`, { method: 'PATCH', data }),
  deleteCompanyTeam: id => request(`/company/teams/${encodeURIComponent(id)}`, { method: 'DELETE', data: {} }),
  assignCompanyMember: (id, data) => request(`/company/teams/${encodeURIComponent(id)}/assignments`, { method: 'PUT', data }),
  removeCompanyMember: (id, username) => request(`/company/teams/${encodeURIComponent(id)}/assignments`, { method: 'DELETE', data: { username } }),
  onboardingProfile: (id, signal) => request(`${prefix(id)}/onboarding-profile`, { signal }),
  saveOnboardingProfile: (id, data) => request(`${prefix(id)}/onboarding-profile`, { method: 'PUT', data }),
  readingPath: (id, signal) => request(`${prefix(id)}/reading-path`, { signal }),
  createReadingStep: (id, data) => request(`${prefix(id)}/reading-path`, { method: 'POST', data }),
  saveReadingStep: (id, stepId, data) => request(`${prefix(id)}/reading-path/${encodeURIComponent(stepId)}`, { method: 'PATCH', data }),
  deleteReadingStep: (id, stepId) => request(`${prefix(id)}/reading-path/${encodeURIComponent(stepId)}`, { method: 'DELETE', data: {} }),
  reorderReadingSteps: (id, stepIds) => request(`${prefix(id)}/reading-path/order`, { method: 'PUT', data: { stepIds } }),
  completeReadingStep: (id, stepId, revision) => request(`${prefix(id)}/reading-path/${encodeURIComponent(stepId)}/completion`, { method: 'PUT', data: { revision } }),
  conversations: (id, signal) => request(`${prefix(id)}/conversations`, { signal }),
  createConversation: id => request(`${prefix(id)}/conversations`, { method: 'POST', data: {} }),
  conversation: (id, conversationId, signal) => request(`${prefix(id)}/conversations/${encodeURIComponent(conversationId)}`, { signal }),
  deleteConversation: (id, conversationId) => request(`${prefix(id)}/conversations/${encodeURIComponent(conversationId)}`, { method: 'DELETE', data: {} }),
  sendTurn: (id, conversationId, question, requestId, signal) => request(`${prefix(id)}/conversations/${encodeURIComponent(conversationId)}/turns`, { method: 'POST', data: { question, requestId }, signal }),
  createProject: (data) => request('/projects', { method: 'POST', data }),
  updateProject: (id, data) => request(prefix(id), { method: 'PATCH', data }),
  addMember: (id, data) => request(`${prefix(id)}/members`, { method: 'POST', data }),
  changeMember: (id, userId, role) => request(`${prefix(id)}/members/${encodeURIComponent(userId)}`, { method: 'PATCH', data: { role } }),
  removeMember: (id, userId) => request(`${prefix(id)}/members/${encodeURIComponent(userId)}`, { method: 'DELETE', data: {} }),
  responsibilities: (id, signal) => request(`${prefix(id)}/responsibilities`, { signal }),
  createResponsibility: (id, data) => request(`${prefix(id)}/responsibilities`, { method: 'POST', data }),
  updateResponsibility: (id, responsibilityId, data) => request(`${prefix(id)}/responsibilities/${encodeURIComponent(responsibilityId)}`, { method: 'PATCH', data }),
  deleteResponsibility: (id, responsibilityId) => request(`${prefix(id)}/responsibilities/${encodeURIComponent(responsibilityId)}`, { method: 'DELETE', data: {} }),
  uploadDocument: (id, data) => request(`${prefix(id)}/documents`, { method: 'POST', data }),
  deleteDocument: (id, documentId) => request(`${prefix(id)}/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE', data: {} }),
  projects: (signal) => request('/projects', { signal }),
  project: (id, signal) => request(prefix(id), { signal }),
  document: (id, documentId, signal) =>
    request(`${prefix(id)}/documents/${encodeURIComponent(documentId)}`, {
      signal,
    }),
  members: (id, signal) => request(`${prefix(id)}/members`, { signal }),
  ask: (id, question, signal, history = []) =>
    request(`${prefix(id)}/ask`, { question, signal, history }),
};
