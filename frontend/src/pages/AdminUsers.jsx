import { useEffect, useState } from 'react';
import { errMsg } from '../api/client';
import { changeRole, listUsers, promoteAdmin, setApproval } from '../api/admin';

const ROLES = ['CITIZEN', 'POLICE', 'NGO_WORKER'];

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    listUsers()
      .then((res) => setUsers(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load users')))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleRole = async (userId, role) => {
    setError(''); setMsg('');
    try {
      await changeRole(userId, role);
      setMsg('Role updated.');
      load();
    } catch (err) {
      setError(errMsg(err, 'Could not change role'));
    }
  };

  const handleApproval = async (userId, approved) => {
    setError(''); setMsg('');
    try {
      await setApproval(userId, approved);
      setMsg(`Account ${approved ? 'approved' : 'revoked'}.`);
      load();
    } catch (err) {
      setError(errMsg(err, 'Could not update approval'));
    }
  };

  const handlePromote = async (userId) => {
    if (!window.confirm('Promote this user to ADMIN? This cannot be undone via this UI.')) return;
    setError(''); setMsg('');
    try {
      await promoteAdmin(userId);
      setMsg('User promoted to ADMIN.');
      load();
    } catch (err) {
      setError(errMsg(err, 'Could not promote user'));
    }
  };

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>User Management</h1>
      {error && <div className="error">{error}</div>}
      {msg && <div className="success">{msg}</div>}
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Username</th><th>Email</th><th>Role</th><th>Approved</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>{u.email || '—'}</td>
                <td>
                  <select
                    value={u.role}
                    onChange={(e) => handleRole(u.id, e.target.value)}
                    disabled={u.role === 'ADMIN'}
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    {u.role === 'ADMIN' && <option value="ADMIN">ADMIN</option>}
                  </select>
                </td>
                <td>
                  {u.role === 'POLICE' ? (
                    u.approved
                      ? <button className="btn btn-ghost" onClick={() => handleApproval(u.id, false)}>Revoke</button>
                      : <button className="btn btn-primary" onClick={() => handleApproval(u.id, true)}>Approve</button>
                  ) : (
                    <span className="muted">N/A</span>
                  )}
                </td>
                <td>
                  {u.role !== 'ADMIN' && (
                    <button className="btn btn-ghost" onClick={() => handlePromote(u.id)}>Promote to Admin</button>
                  )}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={5} className="muted">No users found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
