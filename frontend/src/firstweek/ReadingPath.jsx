import { useEffect, useState } from 'react';
import { ArrowRight, Check, Trash2 } from 'lucide-react';

const empty = { title: '', description: '', documentId: '', focus: '', experience: '' };

export function ReadingPath({ project, client, onSource }) {
  const [path, setPath] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [form, setForm] = useState(empty), [editing, setEditing] = useState(null), [revision, setRevision] = useState(0);
  const manage = path?.canManage === true;
  useEffect(() => {
    const controller = new AbortController(); setPath(null); setError('');
    client.readingPath(project.id, controller.signal).then(value => { if (!controller.signal.aborted) setPath(value); })
      .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [client, project.id, revision]);
  const reload = () => setRevision(value => value + 1);
  async function add(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const data = { ...form, focus: form.focus || null, experience: form.experience || null };
      await (editing ? client.saveReadingStep(project.id, editing, data) : client.createReadingStep(project.id, data));
      setForm(empty); setEditing(null); reload();
    }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  async function complete(step) {
    setBusy(true); setError('');
    try { await client.completeReadingStep(project.id, step.id, step.revision); reload(); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  async function remove(step) {
    if (!confirm(`Remove “${step.title}” from this reading path?`)) return;
    setBusy(true); setError('');
    try { await client.deleteReadingStep(project.id, step.id); reload(); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  async function reorder(index, direction) {
    const steps = path.managedSteps || path.steps;
    const next = index + direction;
    if (next < 0 || next >= steps.length) return;
    const ids = steps.map(step => step.id); [ids[index], ids[next]] = [ids[next], ids[index]];
    setBusy(true); setError('');
    try { await client.reorderReadingSteps(project.id, ids); reload(); }
    catch (failure) { setError(failure.message); } finally { setBusy(false); }
  }
  function edit(step) {
    setEditing(step.id); setForm({ title: step.title, description: step.description, documentId: step.documentId, focus: step.focus || '', experience: step.experience || '' }); setError('');
  }
  const displayedSteps = path?.managedSteps || path?.steps || [];
  return <section className="fw-main-section">
    <h2>Your maintained reading path.</h2>
    <p className="fw-lead">Steps are based on managed project sources. Completion is private to you and does not change your project role or access.</p>
    {path && <p className="fw-section-label">Progress {path.completed} of {path.total}</p>}
    {manage && <form className="fw-admin-form" onSubmit={add}>
      <h3>{editing ? 'Edit reading step' : 'Add a reading step'}</h3>
      {editing && <p className="fw-muted">Changing this step resets its private completion until each member reads the revised material.</p>}
      {!project.documents.some(doc => doc.managed) && <p className="fw-muted">Upload a managed text source in Knowledge before adding a step.</p>}
      <label>Step title<input required maxLength={120} disabled={busy} value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} /></label>
      <label>What to learn<textarea rows={2} maxLength={800} disabled={busy} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} /></label>
      <label>Managed source<select required disabled={busy || !project.documents.some(doc => doc.managed)} value={form.documentId} onChange={event => setForm({ ...form, documentId: event.target.value })}><option value="">Choose a source</option>{project.documents.filter(doc => doc.managed).map(doc => <option key={doc.id} value={doc.id}>{doc.title}</option>)}</select></label>
      <div className="fw-admin-actions"><label>Focus<select disabled={busy} value={form.focus} onChange={event => setForm({ ...form, focus: event.target.value })}><option value="">All focuses</option><option value="ENGINEERING">Engineering</option><option value="PRODUCT">Product</option><option value="DESIGN">Design</option><option value="OPERATIONS">Operations</option></select></label><label>Experience<select disabled={busy} value={form.experience} onChange={event => setForm({ ...form, experience: event.target.value })}><option value="">All experience levels</option><option value="NEW">New</option><option value="EXPERIENCED">Experienced</option></select></label></div>
      <div className="fw-admin-actions"><button className="fw-primary" disabled={busy || !form.title.trim() || !form.documentId}>{busy ? 'Saving…' : editing ? 'Save step' : 'Add reading step'}</button>{editing && <button type="button" className="fw-text-button" disabled={busy} onClick={() => { setEditing(null); setForm(empty); }}>Cancel edit</button>}</div>
    </form>}
    {error && <p className="fw-error" role="alert">{error} <button className="fw-text-button" onClick={reload}>Try again</button></p>}
    {!path ? !error && <p role="status">Loading reading path…</p> : !displayedSteps.length ? <div className="fw-note"><h3>No matching reading steps yet.</h3><p>{manage ? 'Add a step from a managed project source.' : 'A maintainer has not added a step matching your onboarding preferences.'}</p></div> : <><div className="fw-reading-path">{displayedSteps.map((step, index) => <div className="fw-reading-row" key={step.id}><button onClick={() => onSource(step.documentId)}><span className={`fw-step ${step.completed ? 'fw-step-complete' : ''}`}>{step.completed ? <Check size={14} /> : index + 1}</span><span><strong>{step.title}</strong><small>{step.description || 'Open the source to begin.'}</small></span><ArrowRight size={17} /></button>{step.completed ? <span className="fw-muted">Completed</span> : <button className="fw-text-button" disabled={busy} onClick={() => complete(step)}>Mark complete</button>}{manage && <div className="fw-admin-actions"><button className="fw-text-button" disabled={busy} onClick={() => edit(step)}>Edit</button><button className="fw-icon-button" aria-label={`Move ${step.title} up`} disabled={busy || index === 0} onClick={() => reorder(index, -1)}>↑</button><button className="fw-icon-button" aria-label={`Move ${step.title} down`} disabled={busy || index === displayedSteps.length - 1} onClick={() => reorder(index, 1)}>↓</button><button className="fw-icon-button" aria-label={`Remove ${step.title}`} disabled={busy} onClick={() => remove(step)}><Trash2 size={16} /></button></div>}</div>)}</div>{manage && <p className="fw-muted">Maintained steps: {displayedSteps.length}. Your progress above includes only steps matching your saved onboarding preferences.</p>}</>}
  </section>;
}
