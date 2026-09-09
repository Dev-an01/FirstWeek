import { useEffect, useState } from 'react';

export function ProjectForm({ project, client, onSaved, onCancel }) {
  const [name, setName] = useState(project?.name || '');
  const [description, setDescription] = useState(project?.summary || '');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function save(event) {
    event.preventDefault();
    setBusy(true); setMessage('');
    try {
      const result = project ? await client.updateProject(project.id, { name, description })
        : await client.createProject({ name, description });
      onSaved(result);
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  return <form className="fw-admin-form" onSubmit={save}>
    <h2>{project ? 'Project settings' : 'Create a project'}</h2>
    {!project && <p className="fw-muted">You’ll be its first maintainer. Add people from your company after creating it.</p>}
    <label>Project name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} disabled={busy} autoFocus={!project} /></label>
    <label>Description<textarea maxLength={2000} rows={3} value={description} onChange={e => setDescription(e.target.value)} disabled={busy} /></label>
    {message && <p role="alert" className="fw-error">{message}</p>}
    <div className="fw-admin-actions">
      <button className="fw-primary" disabled={busy || !name.trim()}>{busy ? 'Saving…' : project ? 'Save changes' : 'Create project'}</button>
      {onCancel && <button className="fw-text-button" type="button" onClick={onCancel} disabled={busy}>Cancel</button>}
    </div>
  </form>;
}

export function MemberAdministration({ project, client, onChanged }) {
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [username, setUsername] = useState('');
  const [role, setRole] = useState('MEMBER');
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [revision, setRevision] = useState(0);
  const manage = project.membershipRole === 'MAINTAINER';
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    client.members(project.id, controller.signal).then(data => {
      if (!controller.signal.aborted) { setMembers(data.members); setLoading(false); }
    }).catch(failure => {
      if (!controller.signal.aborted) { setError(failure.message); setLoading(false); }
    });
    return () => controller.abort();
  }, [project.id, client, revision]);
  async function mutate(action, success) {
    setBusy(true); setError(''); setMessage('');
    try {
      await action(); setMessage(success); setConfirm(null); setUsername('');
      setRevision(value => value + 1); onChanged();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <section className="fw-main-section">
    <h2>The people behind the project.</h2>
    <p className="fw-muted">Members can read project sources and ask questions. Maintainers also manage project settings and access.</p>
    {manage && <form className="fw-admin-form" onSubmit={event => {
      event.preventDefault(); mutate(() => client.addMember(project.id, { username, role }), 'Member added.');
    }}>
      <h3>Add a company member</h3>
      <p className="fw-muted">Enter the exact username of an active, verified person in your company.</p>
      <label>Username<input required maxLength={100} value={username} onChange={e => setUsername(e.target.value)} disabled={busy} autoComplete="off" /></label>
      <label>Project role<select value={role} onChange={e => setRole(e.target.value)} disabled={busy}>
        <option value="MEMBER">Member</option><option value="MAINTAINER">Maintainer</option>
      </select></label>
      <button className="fw-primary" disabled={busy || !username.trim()}>{busy ? 'Saving…' : 'Add member'}</button>
    </form>}
    {error && <p role="alert" className="fw-error">{error} <button className="fw-text-button" onClick={() => setRevision(v => v + 1)}>Reload members</button></p>}
    {message && <p role="status">{message}</p>}
    {loading ? <p role="status">Loading members…</p> : <ul className="fw-member-list">
      {members.map(member => <li key={member.userId}>
        <div className="fw-member-identity"><strong>{member.firstName} {member.lastName}</strong><span className="fw-muted">@{member.username}{member.title ? ` · ${member.title}` : ''}</span></div>
        {manage ? <div className="fw-admin-actions">
          <label><span className="fw-sr-only">Role for {member.username}</span><select aria-label={`Role for ${member.username}`} value={member.role} disabled={busy} onChange={event => mutate(() => client.changeMember(project.id, member.userId, event.target.value), 'Role updated.')}>
            <option value="MEMBER">Member</option><option value="MAINTAINER">Maintainer</option>
          </select></label>
          {confirm === member.userId ? <>
            <span>Remove access?</span>
            <button className="fw-text-button fw-error" disabled={busy} onClick={() => mutate(() => client.removeMember(project.id, member.userId), 'Member removed.')}>Confirm removal</button>
            <button className="fw-text-button" disabled={busy} onClick={() => setConfirm(null)}>Cancel</button>
          </> : <button className="fw-text-button" disabled={busy} onClick={() => setConfirm(member.userId)}>Remove</button>}
        </div> : <span className="fw-muted">{member.role === 'MAINTAINER' ? 'Maintainer' : 'Member'}</span>}
      </li>)}
    </ul>}
  </section>;
}

export function ResponsibilityAdministration({ project, client }) {
  const empty = { name: '', description: '', status: 'ACTIVE', ownerUserId: '' };
  const [items, setItems] = useState([]), [members, setMembers] = useState([]);
  const [form, setForm] = useState(empty), [editing, setEditing] = useState(null);
  const [message, setMessage] = useState(''), [revision, setRevision] = useState(0);
  const manage = project.membershipRole === 'MAINTAINER';
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([client.responsibilities(project.id, controller.signal), client.members(project.id, controller.signal)])
      .then(([data, people]) => { setItems(data.responsibilities); setMembers(people.members); })
      .catch(error => { if (!controller.signal.aborted) setMessage(error.message); });
    return () => controller.abort();
  }, [client, project.id, revision]);
  const reset = () => { setEditing(null); setForm(empty); };
  async function save(event) {
    event.preventDefault(); setMessage('');
    try {
      const data = { ...form, ownerUserId: form.ownerUserId || null };
      if (editing) await client.updateResponsibility(project.id, editing, data);
      else await client.createResponsibility(project.id, data);
      reset(); setRevision(value => value + 1);
    } catch (error) { setMessage(error.message); }
  }
  return <section className="fw-main-section">
    <h2>Who owns what?</h2><p className="fw-muted">Maintained responsibilities are current, sourced context for answers.</p>
    {manage && <form className="fw-admin-form" onSubmit={save}>
      <label>Responsibility<input required maxLength={120} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /></label>
      <label>Details<textarea maxLength={2000} rows={3} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
      <label>Status<select value={form.status} onChange={e => setForm({ ...form, status: e.target.value })}><option value="ACTIVE">Active</option><option value="BLOCKED">Blocked</option><option value="DONE">Done</option></select></label>
      <label>Owner<select value={form.ownerUserId} onChange={e => setForm({ ...form, ownerUserId: e.target.value })}><option value="">Unassigned</option>{members.map(member => <option key={member.userId} value={member.userId}>{member.firstName} {member.lastName} (@{member.username})</option>)}</select></label>
      <div className="fw-admin-actions"><button className="fw-primary">{editing ? 'Save responsibility' : 'Add responsibility'}</button>{editing && <button type="button" className="fw-text-button" onClick={reset}>Cancel</button>}</div>
    </form>}
    {message && <p role="alert" className="fw-error">{message}</p>}
    {!items.length ? <div className="fw-note"><p>No responsibilities recorded yet.</p></div> : <ul className="fw-member-list">{items.map(item => <li key={item.id}>
      <div className="fw-member-identity"><strong>{item.name}</strong><span className="fw-muted">{item.status.toLowerCase()} · {item.owner ? `${item.owner.firstName} ${item.owner.lastName}` : 'Unassigned'}</span><span>{item.description}</span></div>
      {manage && <div className="fw-admin-actions"><button className="fw-text-button" onClick={() => { setEditing(item.id); setForm({ name: item.name, description: item.description, status: item.status, ownerUserId: item.ownerUserId || '' }); }}>Edit</button><button className="fw-text-button fw-error" onClick={async () => { try { await client.deleteResponsibility(project.id, item.id); setRevision(v => v + 1); } catch (error) { setMessage(error.message); } }}>Delete</button></div>}
    </li>)}</ul>}
  </section>;
}
