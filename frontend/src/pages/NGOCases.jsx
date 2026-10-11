import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errMsg } from '../api/client';
import { listCases } from '../api/ngo';

export default function NGOCases() {
  const [cases, setCases] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCases()
      .then((res) => setCases(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load cases')))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>Assigned Cases</h1>
      {error && <div className="error">{error}</div>}
      {cases.length === 0 ? (
        <div className="card"><p className="muted">No cases have been shared with your NGO yet.</p></div>
      ) : (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr><th>Name</th><th>Status</th><th>Last Seen</th><th>City</th><th>Notes</th><th></th></tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.full_name}</strong></td>
                  <td><span className={`badge badge-${(c.status || '').toLowerCase()}`}>{c.status}</span></td>
                  <td>{c.date_last_seen || '—'}</td>
                  <td>{c.last_seen_city || '—'}</td>
                  <td className="muted">{c.ngo_notes || '—'}</td>
                  <td><Link to={`/persons/${c.id}`}>View →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
