import { useEffect, useState } from 'react';

function TeamForm({ team, busy, onSave }) {
  const [name, setName] = useState(team?.name || ''), [description, setDescription] = useState(team?.description || '');
  return <form className="fw-admin-form" onSubmit={async event => {
    event.preventDefault();
    if (await onSave({ name, description }) && !team) { setName(''); setDescription(''); }
  }}>
    <h3>{team ? 'Edit team' : 'Create a company team'}</h3>
    <label>Team name<input required maxLength={120} disabled={busy} value={name} onChange={e => setName(e.target.value)} /></label>
    <label>Team description<textarea rows={3} maxLength={2000} disabled={busy} value={description} onChange={e => setDescription(e.target.value)} /></label>
    <button className="fw-primary" disabled={busy || !name.trim()}>{busy ? 'Saving…' : team ? 'Save team' : 'Create team'}</button>
  </form>;
}
function Team({ team, canManage, busy, mutate, client }) {
  const [username, setUsername] = useState(''), [assignment, setAssignment] = useState('');
  const [confirm, setConfirm] = useState(null);
  return <details className="fw-company-team">
    <summary><strong>{team.name}</strong><span className="fw-muted">{team.assignments.length} current assignments</span></summary>
    <p>{team.description || 'No description recorded.'}</p>
    <p className="fw-muted">Team updated {new Date(team.updatedAt).toLocaleString()}</p>
    {canManage && <TeamForm team={team} busy={busy} onSave={data => mutate(() => client.saveCompanyTeam(team.id, data), 'Team updated.')} />}
    {!team.assignments.length ? <p className="fw-muted">No current assignments. Ownership has not been recorded here.</p> : <ul className="fw-member-list">
      {team.assignments.map(item => <li key={item.user.username}>
        <div className="fw-member-identity"><strong>{item.user.firstName} {item.user.lastName}</strong><span className="fw-muted">@{item.user.username}</span><span>{item.assignment}</span><span className="fw-muted">Assignment updated {new Date(item.updatedAt).toLocaleString()}</span></div>
        {canManage && <div className="fw-admin-actions">
          <button className="fw-text-button" disabled={busy} onClick={() => { setUsername(item.user.username); setAssignment(item.assignment); }}>Edit assignment for {item.user.username}</button>
          <button className="fw-text-button fw-error" disabled={busy} onClick={() => setConfirm({ kind: 'assignment', username: item.user.username })}>Remove {item.user.username}</button>
        </div>}
      </li>)}
    </ul>}
    {canManage && <>
      <form className="fw-admin-form" onSubmit={async event => {
        event.preventDefault();
        if (await mutate(() => client.assignCompanyMember(team.id, { username, assignment }), 'Assignment saved.')) { setUsername(''); setAssignment(''); }
      }}>
        <h3>Add or update an assignment</h3>
        <p className="fw-muted">Use the exact username of an active, verified company member. This does not grant project access.</p>
        <label>Member username<input required maxLength={100} autoComplete="off" disabled={busy} value={username} onChange={e => setUsername(e.target.value)} /></label>
        <label>Assignment<textarea required rows={2} maxLength={500} disabled={busy} value={assignment} onChange={e => setAssignment(e.target.value)} /></label>
        <div className="fw-admin-actions"><button className="fw-primary" disabled={busy || !username.trim() || !assignment.trim()}>Save assignment</button>
          <button className="fw-text-button" type="button" disabled={busy || !username.trim()} onClick={() => setConfirm({ kind: 'assignment', username })}>Remove assignment by username</button></div>
      </form>
      <button className="fw-text-button fw-error" disabled={busy} onClick={() => setConfirm({ kind: 'team' })}>Delete team</button>
      {confirm && <div className="fw-note" role="group" aria-label="Confirm deletion">
        <p>{confirm.kind === 'team' ? `Delete ${team.name} and all its assignments? People and project access will not be deleted.` : `Remove the team assignment for @${confirm.username}?`}</p>
        <div className="fw-admin-actions"><button className="fw-text-button fw-error" disabled={busy} onClick={async () => {
          const ok = await mutate(() => confirm.kind === 'team' ? client.deleteCompanyTeam(team.id) : client.removeCompanyMember(team.id, confirm.username), 'Removed.');
          if (ok) setConfirm(null);
        }}>Confirm deletion</button><button className="fw-text-button" disabled={busy} onClick={() => setConfirm(null)}>Cancel</button></div>
      </div>}
    </>}
  </details>;
}
export function CompanyTeams({ client }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setData(null); setError('');
    client.companyTeams(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [client, revision]);
  async function mutate(action, success) {
    setBusy(true); setError(''); setMessage('');
    try {
      await action();
      // Read authoritative permissions and data after each change.
      setData(await client.companyTeams()); setMessage(success); return true;
    } catch (failure) { setError(failure.message); return false; }
    finally { setBusy(false); }
  }
  return <div>
    <p className="fw-lead">These maintained teams and assignments are shared with verified people in your company. They do not change project access or establish project ownership.</p>
    {error && <p role="alert" className="fw-error">{error} <button className="fw-text-button" disabled={busy} onClick={() => setRevision(n => n + 1)}>Reload company teams</button></p>}
    {message && <p role="status">{message}</p>}
    {!data && !error && <p role="status">Loading company teams…</p>}
    {data?.canManage && <><p className="fw-note">Changes here clear saved questions and answers across your company’s projects so outdated team details are not retained. Project memberships stay unchanged.</p>
      <TeamForm busy={busy} onSave={body => mutate(() => client.createCompanyTeam(body), 'Team created.')} /></>}
    {data && !data.teams.length && <p className="fw-muted">No company teams recorded yet.{!data.canManage && ' Ask your company administrator to add them.'}</p>}
    {data?.teams.map(team => <Team key={`${team.id}:${team.updatedAt}`} team={team} canManage={data.canManage} busy={busy} mutate={mutate} client={client} />)}
  </div>;
}
