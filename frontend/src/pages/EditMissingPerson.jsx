import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { PersonForm } from './AddMissingPerson';

export default function EditMissingPerson() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [initial, setInitial] = useState(null);
  const [status, setStatus] = useState('ACTIVE');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/persons/${id}`).then((res) => {
      const { images, ...rest } = res.data;
      setInitial(rest);
      setStatus(res.data.status);
    }).catch((err) => setError(errMsg(err, 'Could not load record')));
  }, [id]);

  const submit = async (form) => {
    setBusy(true);
    setError('');
    try {
      const payload = { ...form };
      ['age', 'height_cm'].forEach((k) => { payload[k] = payload[k] === '' ? null : Number(payload[k]); });
      payload.status = status;
      await api.put(`/persons/${id}`, payload);
      navigate(`/persons/${id}`);
    } catch (err) {
      setError(errMsg(err, 'Could not save changes'));
    } finally {
      setBusy(false);
    }
  };

  if (error && !initial) return <div className="error">{error}</div>;
  if (!initial) return <div className="center-page">Loading…</div>;

  return (
    <div className="card" style={{ maxWidth: 640 }}>
      <h2>Edit Missing Person</h2>
      {error && <div className="error">{error}</div>}
      <div className="form" style={{ marginBottom: '1rem' }}>
        <label>Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="ACTIVE">Active</option>
            <option value="FOUND">Found</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
          </select>
        </label>
      </div>
      <PersonForm initial={initial} onSubmit={submit} busy={busy} submitLabel="Save Changes" />
    </div>
  );
}
