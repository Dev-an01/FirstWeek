import { useAuthStore } from '../store/authStore';

const base = import.meta.env.VITE_FIRSTWEEK_API_URL || '/api/firstweek';
async function request(path, { signal, question, history = [] } = {}) {
  const response = await fetch(`${base}${path}`, {
    method: question === undefined ? 'GET' : 'POST',
    credentials: 'include',
    cache: 'no-store',
    signal,
    headers: { 'Content-Type': 'application/json' },
    ...(question === undefined
      ? {}
      : { body: JSON.stringify({ question, history }) }),
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
