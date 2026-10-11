import { useEffect, useState } from 'react';
import { errMsg } from '../api/client';
import { listCases, submitSighting } from '../api/ngo';

export default function SubmitSighting() {
  const [cases, setCases] = useState([]);
  const [form, setForm] = useState({ person_id: '', location: '', description: '' });
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listCases()
      .then((res) => setCases(res.data))
      .catch(() => {});
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    if (!form.person_id) { setError('Please select a case.'); return; }
    setBusy(true); setError(''); setMsg('');
    try {
      await submitSighting(form);
      setMsg('Sighting submitted successfully.');
      setForm({ person_id: '', location: '', description: '' });
    } catch (err) {
      setError(errMsg(err, 'Could not submit sighting'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Submit Sighting</h1>
      <div className="card" style={{ maxWidth: 560 }}>
        {error && <div className="error">{error}</div>}
        {msg && <div className="success">{msg}</div>}
        <form className="form" onSubmit={submit}>
          <label>
            Case
            <select value={form.person_id} onChange={set('person_id')} required>
              <option value="">— Select a case —</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>{c.full_name}</option>
              ))}
            </select>
          </label>
          <label>
            Location
            <input value={form.location} onChange={set('location')} placeholder="Where was the person seen?" />
          </label>
          <label>
            Description
            <textarea value={form.description} onChange={set('description')} rows={4} placeholder="Describe what you observed…" />
          </label>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Submitting…' : 'Submit Sighting'}
          </button>
        </form>
      </div>
    </div>
  );
}
