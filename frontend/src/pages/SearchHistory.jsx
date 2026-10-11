import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

const MODEL_LABELS = { all: 'All models', cnn: 'CNN', arcface: 'ArcFace', mediapipe_knn: 'MediaPipe + KNN' };

const modelLabel = (m) => MODEL_LABELS[m] || m;

/** "2 completed · 1 unavailable" — no raw internal values. */
function modelsSummary(s) {
  const run = s.models_run || 0;
  const unavailable = s.models_unavailable || 0;
  const errored = s.models_errored || 0;
  const completed = Math.max(run - unavailable - errored, 0);
  if (!run) return 'Not run';
  const parts = [];
  if (completed) parts.push(`${completed} completed`);
  if (unavailable) parts.push(`${unavailable} unavailable`);
  if (errored) parts.push(`${errored} error`);
  return parts.join(' · ') || '—';
}

function ResultCell({ item, isRestricted }) {
  const best = item.best_match;
  if (best?.label) {
    return (
      <span>
        <span className="badge badge-match">Match</span>{' '}
        <strong>{best.label}</strong>{' '}
        <span className="muted">via {modelLabel(best.model)}</span>
      </span>
    );
  }
  const run = item.models_run || 0;
  if (run && (item.models_unavailable || 0) === run) {
    return <span className="badge badge-unavailable">Unavailable</span>;
  }
  if ((item.models_errored || 0) > 0 && (item.models_matched || 0) === 0) {
    return <span className="badge badge-nomatch">Error</span>;
  }
  if (isRestricted) {
    return <span className="muted">Submitted — under review</span>;
  }
  return <span className="muted">No reliable match</span>;
}

export default function SearchHistory() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const isRestricted = ['CITIZEN', 'NGO_WORKER'].includes(user?.role);

  useEffect(() => {
    api.get('/search-history', { params: { limit: 100 } })
      .then((res) => setItems(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load history')))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>Search History</h1>
      {isRestricted && (
        <p className="muted">Only recognition history relevant to your reports is shown.</p>
      )}
      {error && <div className="error">{error}</div>}
      {items.length === 0 && !error && (
        <div className="card">
          <h2>No searches yet</h2>
          <p className="muted">
            {isRestricted
              ? 'There is no recognition history for your reports.'
              : 'Run a recognition search first — results will appear here, newest first.'}
          </p>
          {!isRestricted && <Link to="/search">Go to Recognition Search →</Link>}
        </div>
      )}
      {items.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date &amp; Time</th>
                <th>Uploaded Image</th>
                <th>Recognition Result</th>
                <th>Models</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <td>{s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</td>
                  <td>
                    {s.query_image_url ? (
                      <img
                        className="history-thumb"
                        src={s.query_image_url}
                        alt="Uploaded query"
                        loading="lazy"
                      />
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td><ResultCell item={s} isRestricted={isRestricted} /></td>
                  <td>
                    <span className="muted">{modelLabel(s.model)}</span>
                    <br />
                    <span>{modelsSummary(s)}</span>
                  </td>
                  <td><Link to={`/history/${s.id}`}>View</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
