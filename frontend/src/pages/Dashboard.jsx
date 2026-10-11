import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import RecognitionPanel from '../components/RecognitionPanel';
import AddPersonPanel from '../components/AddPersonPanel';
import CitizenDashboard from './CitizenDashboard';

/**
 * Role-aware dashboard.
 * - POLICE / ADMIN (staff): AI recognition screen + registered-dataset tools.
 * - CITIZEN / NGO_WORKER: their own reports / assigned cases only. Protected
 *   recognition and the identity gallery stay hidden (backend enforces this
 *   too — the panels are not even rendered for restricted roles).
 */
export default function Dashboard() {
  const { user } = useAuth();
  const [models, setModels] = useState(null);
  const [stats, setStats] = useState({ persons: 0, searches: 0 });
  const [error, setError] = useState('');

  const staff = user?.role === 'POLICE' || user?.role === 'ADMIN';

  useEffect(() => {
    (async () => {
      try {
        // /persons and /search-history are role-scoped on the backend
        // (citizens see only their own). /recognition/availability is
        // staff-only, so request it only for staff to avoid 403 noise.
        const calls = [
          api.get('/persons', { params: { limit: 1 } }),
          api.get('/search-history', { params: { limit: 1 } }),
        ];
        if (staff) calls.push(api.get('/recognition/availability'));
        const [p, h, m] = await Promise.all(calls);
        setStats({ persons: p.data.length, searches: h.data.length });
        if (m) setModels(m.data);
      } catch (err) {
        setError(errMsg(err, 'Could not load dashboard'));
      }
    })();
  }, [staff]);

  // Citizens get their own upload-based home page (no report form, no
  // recognition UI). Police/Admin keep the panel below untouched.
  if (user?.role === 'CITIZEN') {
    return <CitizenDashboard />;
  }

  return (
    <div>
      <h1>AI-Powered Missing Person Identification System</h1>
      <p className="muted dashboard-sub">
        {staff
          ? 'Upload a photograph and run all three original AI models — CNN, ArcFace, and MediaPipe + KNN — against the registered-person dataset in one step.'
          : 'Track your reports and case updates from this dashboard.'}
      </p>
      {error && <div className="error">{error}</div>}

      {staff && <RecognitionPanel />}

      {staff && <AddPersonPanel />}

      <div className="grid grid-3">
        <div className="card">
          <h3>{staff ? 'Missing Persons' : 'My Reports'}</h3>
          <div className="score">{stats.persons}</div>
          <Link to="/persons">View reports →</Link>
        </div>
        <div className="card">
          <h3>Past Searches</h3>
          <div className="score">{stats.searches}</div>
          <Link to="/history">View history →</Link>
        </div>
        {staff && (
          <div className="card">
            <h3>Registered Persons</h3>
            <p className="muted">Browse the registered-person identity database.</p>
            <Link to="/dataset">Open gallery →</Link>
          </div>
        )}
      </div>

      {staff && (
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
      )}
      <div className="card">
        <h3>Investigation History</h3>
        <p className="muted">Review past recognition searches and results.</p>
        <Link to="/history">Open history →</Link>
      </div>
    </div>
  );
}
