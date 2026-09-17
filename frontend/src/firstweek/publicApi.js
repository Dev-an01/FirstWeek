async function request(route, signal, data) {
  const response = await fetch(`/api/public?route=${encodeURIComponent(route)}`, {
    method: data ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store', signal,
    ...(data ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {}),
  });
  let body;
  try { body = await response.json(); } catch { throw new Error('The public showcase could not be reached. Please try again.'); }
  if (!response.ok) throw new Error(body.error || 'The public showcase could not be reached. Please try again.');
  return body;
}

// No mutation, identity, upload, company or saved-conversation methods.
export const publicApi = {
  projects: signal => request('projects', signal),
  project: (id, signal) => request(`projects/${id}`, signal),
  document: (id, documentId, signal) => request(`projects/${id}/documents/${documentId}`, signal),
  ask: (id, question, signal, history = []) => request(`projects/${id}/ask`, signal, { question, history }),
};
