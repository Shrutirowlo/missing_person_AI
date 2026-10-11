import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { errMsg } from '../api/client';

const EMPTY = { full_name: '', age: '', gender: 'UNKNOWN', height_cm: '', last_seen_location: '', last_seen_city: '', last_seen_state: '', date_last_seen: '', description: '', contact_name: '', contact_phone: '', contact_email: '' };

export function PersonForm({ initial, onSubmit, busy, submitLabel }) {
  const [form, setForm] = useState({ ...EMPTY, ...initial });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <label>Full name*<input value={form.full_name} onChange={set('full_name')} required /></label>
      <div className="form-row">
        <label>Age<input type="number" value={form.age} onChange={set('age')} min={0} max={130} /></label>
        <label>Gender
          <select value={form.gender} onChange={set('gender')}>
            <option value="UNKNOWN">Unknown</option>
            <option value="MALE">Male</option>
            <option value="FEMALE">Female</option>
            <option value="OTHER">Other</option>
          </select>
        </label>
      </div>
      <div className="form-row">
        <label>Height (cm)<input type="number" step="0.1" value={form.height_cm} onChange={set('height_cm')} /></label>
        <label>Date last seen<input type="date" value={form.date_last_seen} onChange={set('date_last_seen')} /></label>
      </div>
      <label>Last known location<input value={form.last_seen_location} onChange={set('last_seen_location')} /></label>
      <div className="form-row">
        <label>City<input value={form.last_seen_city} onChange={set('last_seen_city')} /></label>
        <label>State<input value={form.last_seen_state} onChange={set('last_seen_state')} /></label>
      </div>
      <label>Description<textarea rows={3} value={form.description} onChange={set('description')} /></label>
      <label>Contact name<input value={form.contact_name} onChange={set('contact_name')} /></label>
      <div className="form-row">
        <label>Contact phone<input value={form.contact_phone} onChange={set('contact_phone')} /></label>
        <label>Contact email<input value={form.contact_email} onChange={set('contact_email')} /></label>
      </div>
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
    </form>
  );
}

const clean = (form) => {
  const out = { ...form };
  ['age', 'height_cm'].forEach((k) => { out[k] = out[k] === '' ? null : Number(out[k]); });
  Object.keys(out).forEach((k) => { if (out[k] === '') out[k] = k === 'gender' ? 'UNKNOWN' : out[k]; });
  return out;
};

export default function AddMissingPerson() {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (form) => {
    setBusy(true);
    setError('');
    try {
      const res = await api.post('/persons', clean(form));
      navigate(`/persons/${res.data.id}`);
    } catch (err) {
      setError(errMsg(err, 'Could not create record'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: 640 }}>
      <h2>Add Missing Person</h2>
      {error && <div className="error">{error}</div>}
      <PersonForm onSubmit={submit} busy={busy} submitLabel="Create Record" />
    </div>
  );
}
