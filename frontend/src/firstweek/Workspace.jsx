import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import {
  ArrowRight,
  ArrowUp,
  BookOpen,
  ChevronRight,
  FileText,
  Folder,
  Layers,
  LogOut,
  MessageSquare,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { firstweekApi } from './api';
import './firstweek.css';
import { Brand } from './Brand';
import { Architecture } from './Architecture';
import { OnboardingProfile } from './OnboardingProfile';
import { CompanyTeams } from './CompanyTeams';
import { ReadingPath } from './ReadingPath';
import { ProjectForm, MemberAdministration, ResponsibilityAdministration } from './ProjectAdministration';

const tabs = [
  ['overview', 'Overview'],
  ['architecture', 'Architecture'],
  ['ask', 'Ask FirstWeek'],
  ['knowledge', 'Knowledge'],
  ['team', 'People'],
  ['onboarding', 'Onboarding'],
  ['reading', 'Reading path'],
  ['settings', 'Settings'],
];
const date = (value) =>
  value
    ? new Date(value).toLocaleDateString('en', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Not recorded';

function Notice({ children, error = false, onRetry }) {
  return (
    <div
      className={`fw-notice ${error ? 'fw-error' : ''}`}
      role={error ? 'alert' : 'status'}
    >
      {children}
      {onRetry && (
        <button className="fw-text-button" onClick={onRetry}>
          Try again <ArrowRight size={15} />
        </button>
      )}
    </div>
  );
}

const markdownComponents = {
  img: function SourceImage({ alt }) { return <span>{alt || 'Embedded image omitted'}</span>; },
  a: function SourceLink({ children }) {
    return <span>{children}</span>;
  },
  h2: function SourceHeading({ children }) {
    return (
      <h2
        id={`fw-source-${String(children)
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')}`}
      >
        {children}
      </h2>
    );
  },
};

function Markdown({ children }) {
  return (
    <div className="fw-prose">
      <ReactMarkdown skipHtml components={markdownComponents}>
        {children}
      </ReactMarkdown>
    </div>
  );
}

function KnowledgeAdministration({ project, client, onChanged, onOpen }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const upload = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!file) return;
    setBusy(true); setMessage('');
    try {
      if (file.size > 256 * 1024) throw new Error('Choose a text file no larger than 256 KB.');
      const content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
      await client.uploadDocument(project.id, { filename: file.name, content });
      setFile(null); form.reset(); setMessage('Source uploaded and indexed.'); onChanged();
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };
  const remove = async (document) => {
    if (!confirm(`Delete “${document.title}” from this project?`)) return;
    setBusy(true); setMessage('');
    try { await client.deleteDocument(project.id, document.id); setMessage('Source deleted.'); onChanged(); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  };
  return <section className="fw-main-section">
    <h2>The project, in writing.</h2>
    <p className="fw-muted">Open a source to see the context behind an answer.</p>
    {project.membershipRole === 'MAINTAINER' && <form className="fw-upload" onSubmit={upload}>
      <label><Upload size={18} /> Add a text source<input type="file" accept=".md,.txt,text/markdown,text/plain" required disabled={busy} onChange={event => setFile(event.target.files[0] || null)} /></label>
      <small>Markdown or plain text, up to 256 KB. The source stays inside this project.</small>
      <button className="fw-primary" disabled={busy || !file}>{busy ? 'Working…' : 'Upload and index'}</button>
    </form>}
    {message && <Notice error={!/uploaded|deleted/.test(message)}>{message}</Notice>}
    <div className="fw-knowledge-list">{project.documents.map(doc => (
      <div className="fw-knowledge-row" key={doc.id}>
        <button onClick={() => onOpen(doc.id)}><FileText size={23} /><span><strong>{doc.title}</strong><small>{doc.managed ? 'Managed source' : 'Source snapshot'} · {date(doc.snapshot_at)}</small></span><ArrowRight size={18} /></button>
        {doc.managed && project.membershipRole === 'MAINTAINER' && <button className="fw-icon-button" aria-label={`Delete ${doc.title}`} disabled={busy} onClick={() => remove(doc)}><Trash2 size={17} /></button>}
      </div>))}</div>
    {!project.documents.length && <Notice>No sources have been indexed for this project yet.</Notice>}
  </section>;
}

function ProjectList({ projects, loading, error, onRetry, basePath, client, canCreate, onCreated, publicAccess = false }) {
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);
  const [showCompany, setShowCompany] = useState(false);
  const shown = projects.filter((p) =>
    `${p.name} ${p.description} ${p.status || ''} ${(p.tags || []).join(' ')}`.toLowerCase().includes(filter.toLowerCase())
  );
  return (
    <div className="fw-directory">
      <div className="fw-intro">
        <h1>
          {publicAccess ? 'Projects,' : 'Your first week,'}
          <br />
          <span>with context.</span>
        </h1>
        <p>
          {publicAccess ? 'Explore the projects, follow their architecture, and ask how they work. No account needed.' : <>Get to know the work. Find your way through the code.<br className="fw-desktop-break" /> Start with a project you’re part of.</>}
        </p>
      </div>
      <div className="fw-list-heading">
        <h2>
          {publicAccess ? 'Public projects' : 'Your projects'} <span>{projects.length}</span>
        </h2>
        <label className="fw-search">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="Find a project"
            placeholder="Find a project"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </label>
      </div>
      {canCreate && !creating && <button className="fw-primary fw-create-project" onClick={() => setCreating(true)}>Create project</button>}
      {canCreate && creating && <ProjectForm client={client} onSaved={onCreated} onCancel={() => setCreating(false)} />}
      {loading ? (
        <Notice>{publicAccess ? 'Loading public projects…' : 'Loading your project memberships…'}</Notice>
      ) : error ? (
        <Notice error onRetry={onRetry}>
          {error}
        </Notice>
      ) : !projects.length ? (
        <div className="fw-empty">
          <Folder size={30} />
          <h3>{publicAccess ? 'No projects are published yet.' : 'You haven’t joined a project yet.'}</h3>
          <p>
            {publicAccess ? 'Published project guides will appear here when they are ready.' : 'Ask your company administrator to add you to a project. Its guides and conversations will appear here.'}
          </p>
        </div>
      ) : !shown.length ? (
        <Notice>No projects match “{filter}”. Try another name.</Notice>
      ) : (
        <div className="fw-project-list">
          {shown.map((p) => (
            <Link
              className="fw-project-row"
              key={p.id}
              to={`${basePath}/${p.id}`}
            >
              <span className="fw-project-initial" aria-hidden="true">
                {p.name.slice(0, 2).toUpperCase()}
              </span>
              <span className="fw-project-copy">
                <strong>{p.name}</strong>
                <span>
                  {p.description ||
                    'Project knowledge and getting-started guides.'}
                </span>
                {(p.status || p.tags?.length) && <span className="fw-project-badges">
                  {p.status && <small>{p.status}</small>}
                  {p.tags?.map(tag => <small key={tag}>{tag}</small>)}
                </span>}
              </span>
              <span className="fw-access">
                <ShieldCheck size={14} />
                {publicAccess ? 'Public guide' : 'Member access'}
              </span>
              <ArrowRight size={19} />
            </Link>
          ))}
        </div>
      )}
      {!publicAccess && client.companyTeams && <section className="fw-company-directory">
        <h2>Company teams</h2>
        <button className="fw-text-button" aria-expanded={showCompany} aria-controls="fw-company-directory" onClick={() => setShowCompany(value => !value)}>{showCompany ? 'Hide company teams' : 'Show company teams'}</button>
        <div id="fw-company-directory">{showCompany && <CompanyTeams client={client} />}</div>
      </section>}
      <div className="fw-directory-note">
        <ShieldCheck size={18} />
        <p>
          {publicAccess ? 'Explore freely. The projects stay read-only.' : 'Your workspace is private.'}
          <br />
          <span>{publicAccess ? 'Only published guides are available. Private workspace data is never included.' : 'Only projects you belong to appear here.'}</span>
        </p>
      </div>
    </div>
  );
}

function SourcePanel({ project, selected, onSelect, onClose, client }) {
  const [state, setState] = useState({ loading: false });
  const panel = useRef(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!selected) {
      setState({ loading: false });
      return undefined;
    }
    const controller = new AbortController();
    setState({ loading: true });
    client
      .document(project.id, selected.split('#')[0], controller.signal)
      .then((doc) => {
        if (!controller.signal.aborted) setState({ doc, loading: false });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({ error: error.message, loading: false });
      });
    return () => controller.abort();
  }, [selected, project.id, client, revision]);
  useEffect(() => {
    if (!selected || !state.doc) return;
    const section = selected.split('#')[1];
    const heading =
      section && panel.current?.querySelector(`[id^="fw-source-${section}"]`);
    if (heading) heading.scrollIntoView({ block: 'nearest' });
    else if (window.matchMedia('(max-width: 800px)').matches)
      panel.current?.scrollIntoView({ block: 'start' });
  }, [selected, state.doc]);
  return (
    <aside
      ref={panel}
      className={`fw-sources ${selected ? 'fw-source-open' : ''}`}
      aria-label="Project sources"
    >
      <div className="fw-source-heading">
        <h2>{selected ? 'Source reader' : 'Behind the answers'}</h2>
        {selected ? (
          <button
            className="fw-icon-button"
            aria-label="Close source reader"
            onClick={onClose}
          >
            <X size={19} />
          </button>
        ) : (
          <BookOpen size={19} />
        )}
      </div>
      {selected ? (
        <div className="fw-reader" aria-live="polite">
          {state.loading ? (
            <Notice>Opening source…</Notice>
          ) : state.error ? (
            <Notice error onRetry={() => setRevision((n) => n + 1)}>
              {state.error}
            </Notice>
          ) : (
            state.doc && (
              <>
                <p className="fw-source-date">
                  Source snapshot · {date(state.doc.snapshot_at)}
                </p>
                <Markdown>{state.doc.content}</Markdown>
                {!!state.doc.evidence?.length && <details className="fw-evidence">
                  <summary>Repository evidence</summary>
                  {state.doc.evidence?.map((e) => (
                    <p key={e.path}>
                      <code>{e.path}</code>
                      <small>SHA-256 {e.sha256?.slice(0, 12)}</small>
                    </p>
                  ))}
                </details>}
              </>
            )
          )}
        </div>
      ) : (
        <>
          <p className="fw-muted">
            Every useful answer starts with a source you can inspect.
          </p>
          <div className="fw-source-list">
            {project.documents.map((doc) => (
              <button key={doc.id} onClick={() => onSelect(doc.id)}>
                <FileText size={19} />
                <span>
                  <strong>{doc.title}</strong>
                  <small>Snapshot {date(doc.snapshot_at)}</small>
                </span>
                <ChevronRight size={16} />
              </button>
            ))}
          </div>
          {!project.documents.length && (
            <p className="fw-muted">
              No sources yet. A maintainer needs to add project knowledge.
            </p>
          )}
          <div className="fw-source-foot">
            <ShieldCheck size={18} />
            <p>
              Scoped to this project.
              <br />
              <span>Other projects’ sources are never included.</span>
            </p>
          </div>
        </>
      )}
    </aside>
  );
}

function SavedAsk({ project, client, onSource }) {
  const [params, setParams] = useSearchParams();
  const selected = params.get('conversation');
  const [items, setItems] = useState([]);
  const [row, setRow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const [failedDraft, setFailedDraft] = useState('');
  const [sendError, setSendError] = useState('');
  const attempt = useRef(null);
  useEffect(() => {
    const controller = new AbortController(); let timer;
    setLoading(true); setError(''); setRow(null); setItems([]); onSource(null);
    async function load() {
      try {
        const list = await client.conversations(project.id, controller.signal);
        if (controller.signal.aborted) return;
        setItems(list.conversations);
        if (!selected && list.conversations.length) { setParams({ conversation: list.conversations[0].id }, { replace: true }); return; }
        const value = selected ? await client.conversation(project.id, selected, controller.signal) : null;
        if (controller.signal.aborted) return;
        setRow(value); setLoading(false);
        if (value?.pendingId) timer = setTimeout(load, 2000);
      } catch (failure) { if (!controller.signal.aborted) { setError(failure.message); setLoading(false); } }
    }
    load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [project.id, client, selected, revision]);
  async function create() {
    setBusy(true); setError('');
    try { const value = await client.createConversation(project.id); setFailedDraft(''); setSendError(''); setParams({ conversation: value.id }); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!row || !confirm('Delete this private conversation and all its messages?')) return;
    setBusy(true); setError('');
    try { await client.deleteConversation(project.id, row.id); setFailedDraft(''); setSendError(''); setParams({}); setRevision(n => n + 1); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  const savedClient = { ask: async (projectId, question, signal) => {
    if (!attempt.current || attempt.current.question !== question || attempt.current.conversationId !== selected) {
      attempt.current = { question, conversationId: selected, requestId: crypto.randomUUID() };
    }
    setBusy(true);
    try {
      const value = await client.sendTurn(projectId, selected, question, attempt.current.requestId, signal);
      attempt.current = null; setFailedDraft(''); setSendError(''); setRow(value);
      setItems(list => list.map(item => item.id === value.id ? { ...item, title: value.title } : item));
      return value.turns.at(-1);
    } catch (failure) { setFailedDraft(question); setSendError(failure.name === 'AbortError' ? 'Request stopped in this tab. Reloading its saved status.' : failure.message); setRevision(n => n + 1); throw failure; }
    finally { setBusy(false); }
  } };
  return <>
    <div className="fw-conversation-tools">
      <label>Private conversations<select value={selected || ''} disabled={busy || loading} onChange={event => { setFailedDraft(''); setSendError(''); setParams({ conversation: event.target.value }); }}>
        <option value="" disabled>Select a conversation</option>
        {items.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select></label>
      <button className="fw-text-button" disabled={busy} onClick={create}>New conversation</button>
      {row && <button className="fw-icon-button" aria-label="Delete conversation" disabled={busy} onClick={remove}><Trash2 size={17} /></button>}
    </div>
    {sendError && <div className="fw-conversation-tools"><Notice error>{sendError} Your question is kept below for retry.</Notice></div>}
    {error ? <div className="fw-main-section"><Notice error onRetry={() => setRevision(n => n + 1)}>{error}</Notice></div>
      : loading ? <div className="fw-main-section"><Notice>Loading your conversations…</Notice></div>
      : !row ? <div className="fw-main-section"><h2>Your questions, kept in one place.</h2><p className="fw-lead">Start a private conversation to save answers and pick up where you left off.</p><button className="fw-primary" disabled={busy} onClick={create}>Start a conversation</button></div>
      : row.pendingId ? <div className="fw-main-section"><Notice>Finishing your previous question. Interrupted requests become available to retry within a minute.</Notice><p>{row.pendingQuestion}</p></div>
      : <>{row.pendingQuestion && !sendError && <div className="fw-conversation-tools"><Notice error>The previous answer was interrupted. Your question is ready to retry.</Notice></div>}<Ask key={`${row.id}:${revision}`} project={project} client={savedClient} onSource={onSource} initialTurns={row.turns} initialQuestion={failedDraft || row.pendingQuestion || ''} saved /></>}
  </>;
}

function Ask({ project, client, onSource, initialTurns = [], initialQuestion = '', saved = false, publicAccess = false }) {
  const [question, setQuestion] = useState(initialQuestion);
  const [localTurns, setTurns] = useState(initialTurns);
  const turns = saved ? initialTurns : localTurns;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(null);
  const end = useRef(null);
  const input = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ block: 'nearest' });
  }, [turns.length]);
  async function submit(event) {
    event.preventDefault();
    if (pending || !question.trim()) return;
    const text = question.trim();
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setError('');
    try {
      const history = turns.slice(-3).flatMap((turn) => [
        { role: 'user', content: turn.question },
        { role: 'assistant', content: turn.answer.slice(0, 4000) },
      ]);
      const answer = await client.ask(
        project.id,
        text,
        controller.signal,
        history
      );
      if (!controller.signal.aborted) {
        if (!saved) setTurns((t) => [...t, { question: text, ...answer }]);
        setQuestion('');
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure.message);
    } finally {
      if (!controller.signal.aborted) {
        setPending(false);
        input.current?.focus();
      }
    }
  }
  return (
    <section className="fw-ask" aria-label="Ask about this project">
      {publicAccess && <p className="fw-muted">Public guides only. This conversation is not saved and resets when you leave this tab or reload. Questions and recent messages are sent to the AI provider when AI chat is enabled. Don’t share private information.</p>}
      {!!turns.length && !saved && (
        <button
          className="fw-text-button"
          disabled={pending}
          onClick={() => {
            setTurns([]);
            setQuestion('');
            setError('');
            input.current?.focus();
          }}
        >
          New conversation
        </button>
      )}
      {!turns.length && !pending ? (
        <div className="fw-ask-intro">
          <MessageSquare size={29} strokeWidth={1.5} />
          <h2>
            A little context
            <br />
            goes a long way.
          </h2>
          <p>
            Ask how this project works, where to start,
            <br />
            or what the documentation says.
          </p>
          <div className="fw-prompts">
            {[
              'How does this project work?',
              'Where should I start reading?',
              'What are the current limitations?',
            ].map((q) => (
              <button
                key={q}
                onClick={() => {
                  setQuestion(q);
                  input.current?.focus();
                }}
              >
                {q}
                <ArrowUp size={15} />
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="fw-conversation" aria-live="polite">
          {turns.map((turn, index) => (
            <article className="fw-turn" key={index}>
              <div className="fw-user-message">
                <span>You</span>
                <p>{turn.question}</p>
              </div>
              <div className="fw-answer-heading">
                <Layers size={17} />
                <strong>FirstWeek</strong>
                <span>
                  {turn.mode === 'generated'
                    ? 'Sourced answer'
                    : turn.mode === 'no-evidence'
                      ? 'No matching evidence'
                      : 'Source excerpts'}
                </span>
              </div>
              {turn.notice && <Notice>{turn.notice}</Notice>}
              <Markdown>{turn.answer}</Markdown>
              {turn.mode === 'source-excerpts' && (
                <p className="fw-excerpt-note">
                  Matching passages from your sources. This is not a generated
                  answer.
                </p>
              )}
              <div className="fw-citations">
                {turn.sources.map((source, i) => (
                  <button key={`${source.id}-${i}`} onClick={() => source.documentId && onSource(source.documentId)} className={!source.documentId ? 'fw-responsibility-citation' : undefined}>
                    <span>{i + 1}</span>
                    <span>{source.heading}{!source.documentId && <small>{source.content} · Maintained {date(source.updatedAt)}</small>}</span>
                    {source.documentId && <ArrowRight size={13} />}
                  </button>
                ))}
              </div>
            </article>
          ))}
          <div ref={end} />
        </div>
      )}
      {pending && (
        <div className="fw-pending-turn" role="status">
          <div className="fw-user-message">
            <span>You</span>
            <p>{question}</p>
          </div>
          <p>
            <Layers size={17} /> FirstWeek is reading your project sources…
          </p>
        </div>
      )}
      <form className="fw-composer" onSubmit={submit}>
        {error && <Notice error>{error}</Notice>}
        <label htmlFor="fw-question">Ask about {project.name}</label>
        <div className="fw-input-wrap">
          <textarea
            id="fw-question"
            ref={input}
            rows={2}
            maxLength={2000}
            placeholder="What would you like to understand?"
            value={question}
            disabled={pending}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === 'Enter' &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                submit(event);
              }
            }}
          />
          <button
            className="fw-send"
            disabled={pending || !question.trim()}
            aria-label={pending ? 'Finding sources' : 'Send question'}
            type="submit"
          >
            {pending ? (
              <span className="fw-loading-dot" />
            ) : (
              <ArrowUp size={22} />
            )}
          </button>
        </div>
        <div className="fw-composer-note">
          <span>
            {pending
              ? 'Finding evidence in this project…'
              : 'Answers are limited to this project’s knowledge.'}
          </span>
          <span>{question.length}/2000</span>
        </div>
        {pending && (
          <button
            className="fw-text-button"
            type="button"
            onClick={() => {
              request.current?.abort();
              setPending(false);
            }}
          >
            Cancel request
          </button>
        )}
      </form>
    </section>
  );
}


function ProjectDetail({ id, view, basePath, client, onChanged, publicAccess = false }) {
  const [state, setState] = useState({ loading: true });
  const [selected, setSelected] = useState(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true });
    client
      .project(id, controller.signal)
      .then((project) => {
        if (!controller.signal.aborted) setState({ project });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ error: error.message });
      });
    return () => controller.abort();
  }, [id, client, revision]);
  if (state.loading)
    return (
      <div className="fw-padded">
        <Notice>Loading project knowledge…</Notice>
      </div>
    );
  if (state.error)
    return (
      <div className="fw-padded">
        <h1>We couldn’t open this project.</h1>
        <Notice error onRetry={() => setRevision((n) => n + 1)}>
          {state.error}
        </Notice>
        <Link className="fw-text-button" to={basePath}>
          Back to your projects <ArrowRight size={16} />
        </Link>
      </div>
    );
  const project = publicAccess ? { ...state.project, membershipRole: undefined } : state.project;
  const availableTabs = tabs.filter(([key]) => (!publicAccess || ['overview', 'architecture', 'ask', 'knowledge'].includes(key)) && (key !== 'settings' || project.membershipRole === 'MAINTAINER') && (key !== 'onboarding' || client.onboardingProfile) && (key !== 'reading' || client.readingPath));
  const active = availableTabs.some(([key]) => key === view) ? view : 'overview';
  const refresh = () => { setSelected(null); setRevision(n => n + 1); onChanged(); };
  return (
    <>
      <header className="fw-project-header">
        <div>
          <div className="fw-breadcrumb">
            <Link to={basePath}>Projects</Link>
            <ChevronRight size={13} />
            <span>{project.name}</span>
          </div>
          <h1>{project.name}</h1>
          <p>{project.summary}</p>
          {(project.status || project.tags?.length) && <div className="fw-project-badges">
            {project.status && <small>{project.status}</small>}
            {project.tags?.map(tag => <small key={tag}>{tag}</small>)}
          </div>}
          <div className="fw-stack">
            {project.stack.map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </div>
        {active !== 'ask' && (
          <Link className="fw-primary" to={`${basePath}/${id}/ask`}>
            Ask FirstWeek <ArrowRight size={17} />
          </Link>
        )}
      </header>
      <nav className="fw-tabs" aria-label="Project sections">
        {availableTabs.map(([key, label]) => (
          <NavLink
            aria-current={active === key ? 'page' : undefined}
            className={active === key ? 'fw-tab-active' : ''}
            key={key}
            to={`${basePath}/${id}/${key}`}
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <div className={`fw-project-body ${selected ? 'fw-reading' : ''}`}>
        <div className="fw-main-pane">
          {active === 'ask' ? (
            !publicAccess && client.conversations ? <SavedAsk project={project} client={client} onSource={setSelected} /> : <Ask project={project} client={client} onSource={setSelected} publicAccess={publicAccess} />
          ) : active === 'architecture' ? (
            <Architecture project={project} onSource={setSelected} />
          ) : active === 'onboarding' ? (
            <OnboardingProfile key={project.id} project={project} client={client} />
          ) : active === 'reading' ? (
            <ReadingPath project={project} client={client} onSource={setSelected} />
          ) : active === 'team' ? (
            <><MemberAdministration project={project} client={client} onChanged={refresh} /><ResponsibilityAdministration project={project} client={client} /></>
          ) : active === 'settings' ? (
            <section className="fw-main-section"><ProjectForm project={project} client={client} onSaved={refresh} /></section>
          ) : active === 'knowledge' ? (
            <KnowledgeAdministration project={project} client={client} onChanged={refresh} onOpen={setSelected} />
          ) : project.knowledgeStatus === 'empty' ? (
            <section className="fw-main-section">
              <h2>Your project is ready for its first sources.</h2>
              <p className="fw-lead">Add your team through People. Project documentation has not been indexed yet, so FirstWeek cannot answer questions about this project’s work.</p>
              <Link className="fw-primary" to={`${basePath}/${id}/team`}>Open project people <ArrowRight size={17} /></Link>
            </section>
          ) : (
            <section className="fw-main-section">
              <h2>
                Get your bearings.
                <br />
                Then get into the work.
              </h2>
              <p className="fw-lead">
                {project.summary}. Start with the guide, follow the
                architecture, and ask about anything that needs more context.
              </p>
              {project.architecture && (
                <Link
                  className="fw-architecture-link"
                  to={`${basePath}/${id}/architecture`}
                >
                  <Layers size={28} />
                  <span>
                    <strong>See the architecture</strong>
                    <small>
                      Components, connections, and the flow of data.
                    </small>
                  </span>
                  <ArrowRight size={20} />
                </Link>
              )}
              <h3 className="fw-section-label">Your reading path</h3>
              <div className="fw-reading-path">
                {[
                  [
                    'Understand the project',
                    'Purpose, scope, and the problem it solves.',
                  ],
                  [
                    'Follow the architecture',
                    'The components and how they work together.',
                  ],
                  [
                    'Find your starting point',
                    'Entry points, setup notes, and known limitations.',
                  ],
                ].map(([title, description], i) => (
                  <button
                    key={title}
                    disabled={!project.documents.length}
                    onClick={() =>
                      setSelected(
                        `${project.documents[0].id}#${['about', 'architecture', 'where-to-start'][i]}`
                      )
                    }
                  >
                    <span className="fw-step">{i + 1}</span>
                    <span>
                      <strong>{title}</strong>
                      <small>{description}</small>
                    </span>
                    <ArrowRight size={17} />
                  </button>
                ))}
              </div>
              <div className="fw-note">
                <h3>Don’t know what to ask yet?</h3>
                <p>
                  Try “How does this project work?” FirstWeek will look for
                  relevant passages and show you where they came from.
                </p>
                <Link to={`${basePath}/${id}/ask`} className="fw-text-button">
                  Start a conversation <ArrowRight size={15} />
                </Link>
              </div>
            </section>
          )}
        </div>
        <SourcePanel
          project={project}
          client={client}
          selected={selected}
          onSelect={setSelected}
          onClose={() => setSelected(null)}
        />
      </div>
    </>
  );
}

export default function Workspace({ client = firstweekApi, preview = false, publicAccess = false }) {
  const { projectId, view } = useParams();
  const [state, setState] = useState({ projects: [], loading: true });
  const [revision, setRevision] = useState(0);
  const [logoutError, setLogoutError] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const basePath = publicAccess ? '/showcase' : preview ? '/preview' : '/projects';
  useEffect(() => {
    const controller = new AbortController();
    setState({ projects: [], loading: true });
    client
      .projects(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ projects: data.projects, canCreate: data.canCreate, loading: false });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState({ projects: [], error: error.message, loading: false });
      });
    return () => controller.abort();
  }, [client, revision, user?.id]);
  async function signOut() {
    setSigningOut(true);
    setLogoutError('');
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch {
      setLogoutError('Sign-out failed. Try again.');
      setSigningOut(false);
    }
  }
  return (
    <div className="fw-app">
      <a className="fw-skip" href="#fw-main">
        Skip to workspace
      </a>
      <aside className="fw-rail">
        <Link className="fw-brand-link" to={basePath}>
          <Brand />
        </Link>
        <div className="fw-workspace-label">
          <span className="fw-workspace-avatar">
            {publicAccess ? 'P' : preview ? 'D' : user?.firstName?.[0] || 'W'}
          </span>
          <span>
            {publicAccess ? 'Public showcase' : preview ? 'Demo workspace' : 'Your workspace'}
            <small>{publicAccess ? 'Explore and ask' : 'Project onboarding'}</small>
          </span>
          <ShieldCheck size={15} />
        </div>
        <nav aria-label="Workspace navigation">
          <NavLink className="fw-all-projects" to={basePath}>
            <Folder size={18} />
            All projects<span>{state.projects.length}</span>
          </NavLink>
          {!preview && !publicAccess && (
            <button
              className="fw-mobile-signout"
              aria-label="Sign out"
              disabled={signingOut}
              onClick={signOut}
            >
              <LogOut size={17} />
            </button>
          )}
          <div className="fw-rail-projects">
            {state.projects.map((p) => (
              <Link
                key={p.id}
                className={projectId === p.id ? 'fw-rail-active' : ''}
                to={`${basePath}/${p.id}`}
              >
                <span className="fw-rail-project-dot" />
                {p.name}
              </Link>
            ))}
          </div>
        </nav>
        <div className="fw-rail-bottom">
          <BookOpen size={22} strokeWidth={1.5} />
          <p>
            Less searching.
            <br />
            <strong>More understanding.</strong>
          </p>
          {publicAccess ? <p>Published knowledge only.</p> : preview ? (
            <Link to="/login" className="fw-signout">
              Go to sign in <ArrowRight size={15} />
            </Link>
          ) : (
            <button
              className="fw-signout"
              onClick={signOut}
              disabled={signingOut}
            >
              <LogOut size={15} />
              {signingOut ? 'Signing out…' : 'Sign out'}
            </button>
          )}
          {logoutError && <p role="alert">{logoutError}</p>}
        </div>
      </aside>
      <main id="fw-main" className="fw-workspace">
        {logoutError && (
          <div className="fw-notice fw-error" role="alert">
            {logoutError}
          </div>
        )}
        <div className="fw-topbar">
          <span>
            <ShieldCheck size={14} />
            {publicAccess ? 'Public showcase · read-only projects' : preview
              ? 'Development preview · fictional project'
              : 'Private workspace · project members only'}
          </span>
          <span>{publicAccess ? 'Visitor' : preview ? 'Preview' : user?.firstName || 'Member'}</span>
        </div>
        {projectId ? (
          <ProjectDetail
            key={`${user?.id || 'preview'}:${projectId}`}
            id={projectId}
            view={view}
            basePath={basePath}
            client={client}
            publicAccess={publicAccess}
            onChanged={() => setRevision(n => n + 1)}
          />
        ) : (
          <ProjectList
            projects={state.projects}
            loading={state.loading}
            error={state.error}
            basePath={basePath}
            onRetry={() => setRevision((n) => n + 1)}
            client={client}
            canCreate={!preview && !publicAccess && state.canCreate}
            publicAccess={publicAccess}
            onCreated={project => { setRevision(n => n + 1); navigate(`${basePath}/${project.id}`); }}
          />
        )}
      </main>
    </div>
  );
}
