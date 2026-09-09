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
