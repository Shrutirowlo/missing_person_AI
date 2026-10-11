import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '', email: '', first_name: '', last_name: '' });
  const [role, setRole] = useState('CITIZEN');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setError('');
    setBusy(true);
    try {
      const user = await register({ ...form, requested_role: role });
      // Police signups stay locked until an admin approves them.
      if (user?.role === 'POLICE' && !user?.approved) {
        navigate('/pending-approval');
      } else {
        navigate('/dashboard');
      }
    } catch (err) {
      setError(errMsg(err, 'Registration failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 560, margin: '2rem auto' }}>
      <h2>Create Account</h2>
      {error && <div className="error">{error}</div>}
      <form className="form" onSubmit={submit}>
        <div className="form-row">
          <label>Username<input value={form.username} onChange={set('username')} required minLength={3} /></label>
          <label>Password<input type="password" value={form.password} onChange={set('password')} required minLength={6} /></label>
        </div>
        <div className="form-row">
          <label>First name<input value={form.first_name} onChange={set('first_name')} /></label>
          <label>Last name<input value={form.last_name} onChange={set('last_name')} /></label>
        </div>
        <div className="form-row">
          <label>Email<input type="email" value={form.email} onChange={set('email')} /></label>
        </div>
        <div className="role-pick" role="radiogroup" aria-label="Register as">
          <button
            type="button"
            role="radio"
            aria-checked={role === 'CITIZEN'}
            className={`role-card${role === 'CITIZEN' ? ' role-card-active' : ''}`}
            onClick={() => setRole('CITIZEN')}
          >
            <strong>Citizen</strong>
            <span className="muted">Report missing persons by photo upload. Instant access.</span>
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={role === 'POLICE'}
            className={`role-card${role === 'POLICE' ? ' role-card-active' : ''}`}
            onClick={() => setRole('POLICE')}
          >
            <strong>Police Officer</strong>
            <span className="muted">AI recognition search + case tools. Requires admin approval.</span>
          </button>
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Register'}</button>
      </form>
      <p className="muted">Have an account? <Link to="/login">Login</Link></p>
    </div>
  );
}
