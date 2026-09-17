import { useEffect, useState } from 'react';

export function OnboardingProfile({ project, client }) {
  const [profile, setProfile] = useState(null), [draft, setDraft] = useState(null);
  const [error, setError] = useState(''), [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setProfile(null); setDraft(null); setError(''); setMessage('');
    client.onboardingProfile(project.id, controller.signal).then(value => {
      if (!controller.signal.aborted) { setProfile(value); setDraft(value); }
    }).catch(failure => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [project.id, client, revision]);
  const changed = draft && (draft.onboardingRole !== profile.onboardingRole || draft.onboardingExperience !== profile.onboardingExperience);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      const value = await client.saveOnboardingProfile(project.id, {
        onboardingRole: draft.onboardingRole, onboardingExperience: draft.onboardingExperience });
      setProfile(value); setDraft(value); setMessage('Preferences saved for this project. Your saved conversations have been reset.');
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <section className="fw-main-section">
    <h2>Your way into the project.</h2>
    <p className="fw-lead">Choose how FirstWeek explains this project to you. These private preferences do not change your access or assign responsibilities.</p>
    {!draft && !error && <p role="status">Loading your preferences…</p>}
    {draft && <form className="fw-admin-form" onSubmit={save} aria-describedby="fw-profile-note">
      <label>Onboarding focus<select disabled={busy} value={draft.onboardingRole || ''} onChange={event => { setDraft({ ...draft, onboardingRole: event.target.value || null }); setMessage(''); }}>
        <option value="">No preference</option><option value="ENGINEERING">Engineering</option>
        <option value="PRODUCT">Product</option><option value="DESIGN">Design</option><option value="OPERATIONS">Operations</option>
      </select></label>
      <label>Explanation level<select disabled={busy} value={draft.onboardingExperience || ''} onChange={event => { setDraft({ ...draft, onboardingExperience: event.target.value || null }); setMessage(''); }}>
        <option value="">No preference</option><option value="NEW">Explain the fundamentals</option>
        <option value="EXPERIENCED">Focus on project-specific details</option>
      </select></label>
      <p id="fw-profile-note" className="fw-muted">Saving changed preferences clears the questions and answers in your saved conversations for this project. Other members’ conversations are unaffected. Source excerpts stay unchanged when generated answers are unavailable.</p>
      <button className="fw-primary" disabled={busy || !changed}>{busy ? 'Saving…' : 'Save preferences'}</button>
    </form>}
    {error && <p role="alert" className="fw-error">{error} {!draft && <button className="fw-text-button" onClick={() => setRevision(value => value + 1)}>Try again</button>}</p>}
    {message && <p role="status">{message}</p>}
  </section>;
}
