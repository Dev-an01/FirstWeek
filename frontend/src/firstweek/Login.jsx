import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, ShieldCheck } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { Brand } from './Brand';
import './firstweek.css';

export function LoginPage() {
  const { login, isAuthenticated } = useAuthStore();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  useEffect(() => {
    if (isAuthenticated) navigate('/projects', { replace: true });
  }, [isAuthenticated, navigate]);
  async function submit(event) {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      await login(identifier.trim(), password);
    } catch (failure) {
      setError(
        failure.message || 'Sign-in failed. Check your details and try again.'
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="fw-login">
      <section className="fw-login-story">
        <Brand />
        <div>
          <h1>
            New project.
            <br />
            Familiar ground.
            <br />
            <span>Start here.</span>
          </h1>
          <p>
            The context, documentation, and people you need to find your feet.
            All in your project’s private workspace.
          </p>
        </div>
        <footer>
          <ShieldCheck size={17} />
          Knowledge stays with the people it belongs to.
        </footer>
      </section>
      <main className="fw-login-form-side">
        <form className="fw-login-form" onSubmit={submit}>
          <h2>Welcome to FirstWeek.</h2>
          <p>
            Sign in to pick up the context.
            <br />
            Your projects are waiting for you.
          </p>
          <label htmlFor="fw-identifier">Email or username</label>
          <input
            id="fw-identifier"
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            placeholder="you@company.com"
            disabled={pending}
          />
          <label htmlFor="fw-password">Password</label>
          <input
            id="fw-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="Enter your password"
            disabled={pending}
          />
          {error && (
            <div className="fw-notice fw-error" role="alert">
              {error}
            </div>
          )}
          <button className="fw-primary" disabled={pending}>
            {pending ? 'Signing in…' : 'Sign in'}
            <ArrowRight size={17} />
          </button>
          <div className="fw-login-links">
            <Link to="/forgot-password">Forgot password?</Link>
            <Link to="/signup">Create an account</Link>
          </div>
        </form>
      </main>
    </div>
  );
}
