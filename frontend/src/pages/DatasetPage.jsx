import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';

export default function DatasetPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/dataset/registered')
      .then((res) => setData(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load registered persons')))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>Registered Persons</h1>
      {error && <div className="error">{error}</div>}
      {data && (
        <>
          <p className="muted">
            {data.imported
              ? `${data.count} registered identities imported from the dataset.`
              : 'No registered-person records found. Run the dataset import from Admin → Dataset Management.'}
          </p>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr><th>Identity</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {(data.identities || []).map((item) => (
                  <tr key={item.identity || item.id}>
                    <td><strong>{item.identity || item.id}</strong></td>
                    <td>
                      <Link to={`/dataset/${item.identity || item.id}`}>View →</Link>
                    </td>
                  </tr>
                ))}
                {(data.identities || []).length === 0 && (
                  <tr><td colSpan={2} className="muted">No identities.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
