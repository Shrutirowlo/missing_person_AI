import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function MissingPersons() {
  const { user } = useAuth();
  const [persons, setPersons] = useState([]);
  const isCitizen = user?.role === 'CITIZEN';
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/persons', { params: { q: q || undefined, status: status || undefined, limit: 100 } });
      setPersons(res.data);
    } catch (err) {
      setError(errMsg(err, 'Could not load persons'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <div className="toolbar">
        <h1 style={{ margin: 0, marginRight: 'auto' }}>Missing Persons</h1>
        {!isCitizen && <Link className="btn btn-primary" to="/persons/new">+ Add Missing Person</Link>}
      </div>
      <div className="toolbar">
        <input placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="FOUND">Found</option>
          <option value="RESOLVED">Resolved</option>
          <option value="CLOSED">Closed</option>
        </select>
        <button className="btn btn-secondary" onClick={load}>Filter</button>
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? <p className="muted">Loading…</p> : (
        <div className="card table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Age</th><th>Gender</th><th>Status</th><th>Photos</th><th></th></tr></thead>
            <tbody>
              {persons.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/persons/${p.id}`}>{p.full_name}</Link></td>
                  <td>{p.age ?? '—'}</td>
                  <td>{p.gender}</td>
                  <td><span className={`badge badge-${p.status.toLowerCase()}`}>{p.status}</span></td>
                  <td>{p.images?.length || 0}</td>
                  <td><Link to={`/persons/${p.id}/edit`}>Edit</Link></td>
                </tr>
              ))}
              {persons.length === 0 && <tr><td colSpan={6} className="muted">No records yet.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
