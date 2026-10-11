import { useState } from 'react';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Profile() {
  const { user } = useAuth();
  const [form, setForm] = useState({ first_name: user?.first_name || '', last_name: user?.last_name || '', email: user?.email || '' });
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    setError('');
    try {
      await api.patch('/auth/profile', form);
      setMsg('Profile updated. It will refresh on next login.');
    } catch (err) {
      setError(errMsg(err, 'Could not update profile'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 560 }}>
      <h2>Profile</h2>
      <p className="muted">Username: {user?.username} · Role: {user?.role}</p>
      {msg && <div className="success">{msg}</div>}
      {error && <div className="error">{error}</div>}
      <form className="form" onSubmit={save}>
        <div className="form-row">
          <label>First name<input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></label>
          <label>Last name<input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></label>
        </div>
        <label>Email<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save Profile'}</button>
      </form>
    </div>
  );
}
