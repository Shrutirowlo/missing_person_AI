import { useEffect, useState } from 'react';
import { errMsg } from '../api/client';
import { getActivity } from '../api/ngo';

export default function NGOActivity() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getActivity()
      .then((res) => setItems(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load activity')))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>My Activity</h1>
      {error && <div className="error">{error}</div>}
      {items.length === 0 ? (
        <div className="card"><p className="muted">No activity recorded yet.</p></div>
      ) : (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Case</th><th>Location</th><th>Description</th></tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td>
                  <td>{item.person_id}</td>
                  <td>{item.location || '—'}</td>
                  <td className="muted">{item.description || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
