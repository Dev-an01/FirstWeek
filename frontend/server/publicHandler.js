import { publicCollection } from './publicCollection.js';
import { generate, reserveChat, retrieve } from './publicChat.js';

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}
async function readBody(req) {
  if (Number(req.headers['content-length']) > 32000) throw new Error('body');
  if (req.body !== undefined) {
    const value = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    if (Buffer.byteLength(value) > 32000) throw new Error('body');
    return JSON.parse(value);
  }
  let body = '';
  req.setEncoding('utf8');
  for await (const chunk of req) {
    body += chunk.toString();
    if (Buffer.byteLength(body) > 32000) throw new Error('body');
  }
  return JSON.parse(body);
}
function validBody(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).some(key => !['question', 'history'].includes(key))) return false;
  if (typeof body.question !== 'string' || !body.question.trim() || body.question.length > 2000) return false;
  const history = body.history ?? [];
  return Array.isArray(history) && history.length <= 6 && history.every(row => row && Object.keys(row).every(key => ['role', 'content'].includes(key)) && ['user', 'assistant'].includes(row.role) && typeof row.content === 'string' && row.content.length > 0 && row.content.length <= 4000);
}
const metadata = project => ({
  id: project.id, name: project.name, description: project.description,
  visibility: 'public', status: project.status, tags: project.tags || [],
});

export function createPublicHandler({ env = process.env, fetcher = fetch, collection = publicCollection } = {}) {
  return async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    const url = new URL(req.url, 'http://public.local');
    const routes = url.searchParams.getAll('route');
    if (routes.length !== 1) return send(res, 404, { error: 'Public resource not found.' });
    const parts = routes[0].split('/');
    if (parts[0] !== 'projects') return send(res, 404, { error: 'Public resource not found.' });
    if (parts.length === 1 && req.method === 'GET') return send(res, 200, { canCreate: false, projects: collection.map(metadata) });
    const project = collection.find(item => item.id === parts[1]);
    if (!project) return send(res, 404, { error: 'Public project not found.' });
    if (parts.length === 2 && req.method === 'GET') return send(res, 200, {
      ...metadata(project), summary: project.summary, stack: project.stack, architecture: project.architecture,
      documents: project.documents.map(({ id, title, snapshot_at }) => ({ id, title, snapshot_at })),
    });
    if (parts.length === 4 && parts[2] === 'documents' && req.method === 'GET') {
      const doc = project.documents.find(item => item.id === parts[3]);
      return doc ? send(res, 200, { id: doc.id, title: doc.title, snapshot_at: doc.snapshot_at, content: doc.content }) : send(res, 404, { error: 'Public source not found.' });
    }
    if (parts.length !== 3 || parts[2] !== 'ask') return send(res, 404, { error: 'Public resource not found.' });
    if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); return send(res, 405, { error: 'Use POST for public chat.' }); }
    // Same-origin browser UI only. No client-supplied host, identity or scope.
    if (!env.FIRSTWEEK_PUBLIC_ORIGIN || req.headers.origin !== env.FIRSTWEEK_PUBLIC_ORIGIN || req.headers['sec-fetch-site'] === 'cross-site') {
      return send(res, 403, { error: 'Open this demo at its configured website address and try again.' });
    }
    if (req.headers['content-type']?.split(';')[0].trim() !== 'application/json') return send(res, 415, { error: 'Send a JSON question.' });
    let body;
    try { body = await readBody(req); } catch { return send(res, 400, { error: 'Send a valid question within the size limit.' }); }
    if (!validBody(body)) return send(res, 400, { error: 'Use a question up to 2,000 characters and at most six short conversation messages.' });
    const question = body.question.trim();
    const history = (body.history || []).map(({ role, content }) => ({ role, content }));
    const sources = retrieve(project, question, history);
    // Ask normally runs the complete retrieval -> prompt -> LLM pipeline.
    // Excerpts are an explicit offline/debug choice, never a silent fallback.
    if (env.FIRSTWEEK_PUBLIC_GENERATE === 'false') return send(res, 200, {
      answer: sources.length ? sources.map((source, i) => `[${i + 1}] ${source.heading}\n\n${source.content}`).join('\n\n') : 'The public guide does not contain matching evidence. Try asking about the architecture or limitations.',
      sources, mode: sources.length ? 'source-excerpts' : 'no-evidence', retrieval: 'public-keyword',
    });
    if (env.FIRSTWEEK_PUBLIC_GENERATE !== undefined && env.FIRSTWEEK_PUBLIC_GENERATE !== 'true') {
      return send(res, 503, { error: 'AI chat configuration is invalid. The site owner needs to check the generation setting.' });
    }
    if (env.FIRSTWEEK_PUBLIC_GROQ_FALLBACK !== undefined && !['true', 'false'].includes(env.FIRSTWEEK_PUBLIC_GROQ_FALLBACK)) {
      return send(res, 503, { error: 'AI chat configuration is invalid. The site owner needs to check the fallback setting.' });
    }
    const providerKeys = [env.OPENAI_API_KEY, env.OPENROUTER_API_KEY];
    if (env.FIRSTWEEK_PUBLIC_GROQ_FALLBACK === 'true') providerKeys.push(env.GROQ_API_KEY);
    if (!providerKeys.some(key => typeof key === 'string' && key.trim())) {
      return send(res, 503, { error: 'AI chat is not configured yet. You can still browse the public guides.' });
    }
    try {
      // Vercel supplies/overwrites this header. Local mode uses one shared bucket;
      // never trust arbitrary X-Forwarded-For sent by visitors.
      const ip = env.VERCEL === '1' ? req.headers['x-vercel-forwarded-for'] : 'local-demo';
      if (typeof ip !== 'string' || !ip || ip.length > 256) throw new Error('limits-unavailable');
      if (!await reserveChat(env, ip, fetcher)) {
        res.setHeader('Retry-After', '60');
        return send(res, 429, { error: 'The public demo has reached a usage limit. Please try later; the guides remain available.' });
      }
      return send(res, 200, await generate(project, question, history, sources, env, fetcher));
    } catch {
      return send(res, 503, { error: 'AI chat is temporarily unavailable. Please try later or read the public guides.' });
    }
  };
}

export default createPublicHandler();
