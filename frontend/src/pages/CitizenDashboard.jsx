import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import CitizenUploadPanel from '../components/CitizenUploadPanel';
import { useAuth } from '../context/AuthContext';

const STATUS_LABEL = { ACTIVE: 'Active', FOUND: 'Found', RESOLVED: 'Resolved', CLOSED: 'Closed' };

export default function CitizenDashboard() {
  const { user } = useAuth();
  const [reports, setReports] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await api.get('/persons', { params: { limit: 100 } });
      setReports(res.data);
    } catch (err) {
      setError(errMsg(err, 'Could not load reports'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <h1>Welcome, {user?.first_name || user?.username}</h1>
      <p className="muted dashboard-sub">
        Upload a photograph to report a missing person — it is stored and sent
        for review by authorized personnel.
      </p>
      {error && <div className="error">{error}</div>}

      <CitizenUploadPanel onUploaded={load} />

      <div className="card">
        <h3>My Reports ({reports.length})</h3>
        {loading ? <p className="muted">Loading…</p> : reports.length === 0 ? (
          <p className="muted">No reports yet — your submitted reports will appear here.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Status</th><th>Photos</th><th>Submitted</th><th></th></tr></thead>
              <tbody>
                {reports.map((p) => (
                  <tr key={p.id}>
                    <td><Link to={`/persons/${p.id}`}>{p.full_name}</Link></td>
                    <td><span className={`badge badge-${(p.status || '').toLowerCase()}`}>{STATUS_LABEL[p.status] || p.status}</span></td>
                    <td>{p.images?.length || 0}</td>
                    <td>{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                    <td><Link to={`/persons/${p.id}`}>View</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <p className="muted">
          Your reports are reviewed by authorized personnel. Recognition results and identity
          information are available to police and administrators only.
        </p>
        <Link to="/profile">Edit Profile →</Link>
      </div>
    </div>
  );
}
