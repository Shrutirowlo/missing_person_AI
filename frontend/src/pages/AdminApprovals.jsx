import { useEffect, useState } from 'react';
import { errMsg } from '../api/client';
import { listUsers, setApproval } from '../api/admin';

export default function AdminApprovals() {
  const [pending, setPending] = useState([]);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    listUsers()
      .then((res) => {
        setPending(res.data.filter((u) => u.role === 'POLICE' && !u.approved));
      })
      .catch((err) => setError(errMsg(err, 'Could not load users')))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const approve = async (userId) => {
    setError(''); setMsg('');
    try {
      await setApproval(userId, true);
      setMsg('Account approved.');
      load();
    } catch (err) {
      setError(errMsg(err, 'Could not approve account'));
    }
  };

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>Police Approvals</h1>
      {error && <div className="error">{error}</div>}
      {msg && <div className="success">{msg}</div>}
      {pending.length === 0 ? (
        <div className="card"><p className="muted">No pending police approvals.</p></div>
      ) : (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr><th>Username</th><th>Email</th><th>Created</th><th>Action</th></tr>
            </thead>
            <tbody>
              {pending.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.email || '—'}</td>
                  <td>{u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
                  <td>
                    <button className="btn btn-primary" onClick={() => approve(u.id)}>Approve</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
