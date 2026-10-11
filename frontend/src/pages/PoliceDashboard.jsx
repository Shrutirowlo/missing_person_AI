import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import RecognitionPanel from '../components/RecognitionPanel';

export default function PoliceDashboard() {
  const { user } = useAuth();
  const [models, setModels] = useState(null);
  const [stats, setStats] = useState({ persons: 0, searches: 0 });
  const [error, setError] = useState('');

  const approved = user?.approved === true;

  useEffect(() => {
    if (!approved) return;
    (async () => {
      try {
        const [p, h, m] = await Promise.all([
          api.get('/persons', { params: { limit: 1 } }),
          api.get('/search-history', { params: { limit: 1 } }),
          api.get('/recognition/availability'),
        ]);
        setStats({ persons: p.data.length, searches: h.data.length });
        setModels(m.data);
      } catch (err) {
        setError(errMsg(err, 'Could not load dashboard'));
      }
    })();
  }, [approved]);

  // Unapproved police accounts cannot access recognition yet.
  if (!approved) {
    return (
      <div>
        <h1>AI-Powered Missing Person Identification System</h1>
        <div className="card">
          <h2>Welcome, {user?.first_name || user?.username}</h2>
          <p className="muted">
            Your police account is pending admin approval. AI recognition will unlock
            on this dashboard once an administrator approves your account.
          </p>
          <Link className="btn btn-secondary" to="/persons/new">Report a missing person →</Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1>AI-Powered Missing Person Identification System</h1>
      <p className="muted dashboard-sub">
        Upload a photograph and run all three original AI models — CNN, ArcFace, and
        MediaPipe + KNN — against the registered-person dataset in one step.
      </p>
      {error && <div className="error">{error}</div>}

      <RecognitionPanel />

      <div className="grid grid-3">
        <div className="card">
          <h3>Missing Persons</h3>
          <div className="score">{stats.persons}</div>
          <Link to="/persons">View all reports →</Link>
        </div>
        <div className="card">
          <h3>Past Searches</h3>
          <div className="score">{stats.searches}</div>
          <Link to="/history">View history →</Link>
        </div>
        <div className="card">
          <h3>Registered Persons</h3>
          <p className="muted">Browse the registered-person identity database.</p>
          <Link to="/dataset">Open gallery →</Link>
        </div>
      </div>

      <div className="card">
        <h3>Model Availability</h3>
        {!models && <p className="muted">Loading…</p>}
        {models && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Model</th><th>Status</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {Object.entries(models).map(([name, info]) => (
                  <tr key={name}>
                    <td><strong>{name}</strong></td>
                    <td>
                      {info.available
                        ? <span className="badge badge-match">Available</span>
                        : <span className="badge badge-unavailable">Unavailable</span>}
                    </td>
                    <td className="muted">
                      {info.available ? 'Original artifacts loaded read-only.' : info.error}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="card">
        <h3>Investigation History</h3>
        <p className="muted">Review past recognition searches and results.</p>
        <Link to="/history">Open history →</Link>
      </div>
    </div>
  );
}
