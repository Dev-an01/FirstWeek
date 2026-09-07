import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom';
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
  X,
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { firstweekApi } from './api';
import './firstweek.css';
import { Brand } from './Brand';
import { Architecture } from './Architecture';

const tabs = [
  ['overview', 'Overview'],
  ['architecture', 'Architecture'],
  ['ask', 'Ask FirstWeek'],
  ['knowledge', 'Knowledge'],
  ['team', 'People'],
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

function ProjectList({ projects, loading, error, onRetry, basePath }) {
  const [filter, setFilter] = useState('');
  const shown = projects.filter((p) =>
    `${p.name} ${p.description}`.toLowerCase().includes(filter.toLowerCase())
  );
  return (
    <div className="fw-directory">
      <div className="fw-intro">
        <h1>
          Your first week,
          <br />
          <span>with context.</span>
        </h1>
        <p>
          Get to know the work. Find your way through the code.
          <br className="fw-desktop-break" /> Start with a project you’re part
          of.
        </p>
      </div>
      <div className="fw-list-heading">
        <h2>
          Your projects <span>{projects.length}</span>
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
      {loading ? (
        <Notice>Loading your project memberships…</Notice>
      ) : error ? (
        <Notice error onRetry={onRetry}>
          {error}
        </Notice>
      ) : !projects.length ? (
        <div className="fw-empty">
          <Folder size={30} />
          <h3>You haven’t joined a project yet.</h3>
          <p>
            Ask your company administrator to add you to a project. Its guides
            and conversations will appear here.
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
              </span>
              <span className="fw-access">
                <ShieldCheck size={14} />
                Member access
              </span>
              <ArrowRight size={19} />
            </Link>
          ))}
        </div>
      )}
      <div className="fw-directory-note">
        <ShieldCheck size={18} />
        <p>
          Your workspace is private.
          <br />
          <span>Only projects you belong to appear here.</span>
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
                <details className="fw-evidence">
                  <summary>Repository evidence</summary>
                  {state.doc.evidence?.map((e) => (
                    <p key={e.path}>
                      <code>{e.path}</code>
                      <small>SHA-256 {e.sha256?.slice(0, 12)}</small>
                    </p>
                  ))}
                </details>
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

function Ask({ project, client, onSource }) {
  const [question, setQuestion] = useState('');
  const [turns, setTurns] = useState([]);
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
        setTurns((t) => [...t, { question: text, ...answer }]);
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
      {!!turns.length && (
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
                  <button
                    key={`${source.id}-${i}`}
                    onClick={() => onSource(source.documentId)}
                  >
                    <span>{i + 1}</span>
                    {source.heading}
                    <ArrowRight size={13} />
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

function People({ project, client }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    client
      .members(project.id, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState(data);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setState({ error: error.message });
      });
    return () => controller.abort();
  }, [project.id, client]);
  return (
    <section className="fw-main-section">
      <h2>The people behind the project.</h2>
      <p className="fw-muted">
        Membership tells you who is here. Responsibilities need to be confirmed
        by a maintainer.
      </p>
      {state.loading ? (
        <Notice>Loading project members…</Notice>
      ) : state.error ? (
        <Notice error>{state.error}</Notice>
      ) : (
        <div className="fw-people">
          {state.members?.length ? (
            state.members.map((m) => (
              <div key={m.userId}>
                <span className="fw-project-initial">
                  {m.firstName?.slice(0, 1)}
                  {m.lastName?.slice(0, 1)}
                </span>
                <span>
                  <strong>
                    {m.firstName} {m.lastName}
                  </strong>
                  <small>{m.title || 'Project member'}</small>
                </span>
                <span className="fw-muted">
                  {m.role === 'MAINTAINER' ? 'Maintainer' : 'Member'}
                </span>
              </div>
            ))
          ) : (
            <Notice>No member details are available.</Notice>
          )}
        </div>
      )}
      <div className="fw-note">
        <h3>Who owns what?</h3>
        <p>
          Area ownership has not been recorded yet. FirstWeek won’t infer
          responsibilities from commit history or job titles.
        </p>
      </div>
    </section>
  );
}

function ProjectDetail({ id, view, basePath, client }) {
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
  const { project } = state;
  const active = tabs.some(([key]) => key === view) ? view : 'overview';
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
        {tabs.map(([key, label]) => (
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
            <Ask project={project} client={client} onSource={setSelected} />
          ) : active === 'architecture' ? (
            <Architecture project={project} onSource={setSelected} />
          ) : active === 'team' ? (
            <People project={project} client={client} />
          ) : active === 'knowledge' ? (
            <section className="fw-main-section">
              <h2>The project, in writing.</h2>
              <p className="fw-muted">
                Open a source to see the context behind an answer.
              </p>
              <div className="fw-knowledge-list">
                {project.documents.map((doc) => (
                  <button key={doc.id} onClick={() => setSelected(doc.id)}>
                    <FileText size={23} />
                    <span>
                      <strong>{doc.title}</strong>
                      <small>Source snapshot · {date(doc.snapshot_at)}</small>
                    </span>
                    <ArrowRight size={18} />
                  </button>
                ))}
              </div>
              {!project.documents.length && (
                <Notice>
                  No sources have been indexed for this project yet.
                </Notice>
              )}
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

export default function Workspace({ client = firstweekApi, preview = false }) {
  const { projectId, view } = useParams();
  const [state, setState] = useState({ projects: [], loading: true });
  const [revision, setRevision] = useState(0);
  const [logoutError, setLogoutError] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const basePath = preview ? '/preview' : '/projects';
  useEffect(() => {
    const controller = new AbortController();
    setState({ projects: [], loading: true });
    client
      .projects(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted)
          setState({ projects: data.projects, loading: false });
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
            {preview ? 'D' : user?.firstName?.[0] || 'W'}
          </span>
          <span>
            {preview ? 'Demo workspace' : 'Your workspace'}
            <small>Project onboarding</small>
          </span>
          <ShieldCheck size={15} />
        </div>
        <nav aria-label="Workspace navigation">
          <NavLink className="fw-all-projects" to={basePath}>
            <Folder size={18} />
            All projects<span>{state.projects.length}</span>
          </NavLink>
          {!preview && (
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
          {preview ? (
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
            {preview
              ? 'Development preview · fictional project'
              : 'Private workspace · project members only'}
          </span>
          <span>{preview ? 'Preview' : user?.firstName || 'Member'}</span>
        </div>
        {projectId ? (
          <ProjectDetail
            key={`${user?.id || 'preview'}:${projectId}`}
            id={projectId}
            view={view}
            basePath={basePath}
            client={client}
          />
        ) : (
          <ProjectList
            projects={state.projects}
            loading={state.loading}
            error={state.error}
            basePath={basePath}
            onRetry={() => setRevision((n) => n + 1)}
          />
        )}
      </main>
    </div>
  );
}
