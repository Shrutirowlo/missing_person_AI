import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function PersonDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isPoliceOrAdmin = ['POLICE', 'ADMIN'].includes(user?.role);
  const [person, setPerson] = useState(null);
  const [error, setError] = useState('');
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const res = await api.get(`/persons/${id}`);
      setPerson(res.data);
    } catch (err) {
      setError(errMsg(err, 'Could not load record'));
    }
  };

  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async () => {
    if (!files.length) return;
    setUploading(true);
    setMsg('');
    setError('');
    try {
      const fd = new FormData();
      [...files].forEach((f) => fd.append('files', f));
      await api.post(`/images/persons/${id}`, fd);
      setFiles([]);
      setMsg('Photos uploaded and linked to this record.');
      await load();
    } catch (err) {
      setError(errMsg(err, 'Upload failed'));
    } finally {
      setUploading(false);
    }
  };

  const remove = async () => {
    if (!window.confirm('Archive this record? It will be hidden but not permanently deleted.')) return;
    try {
      await api.delete(`/persons/${id}`);
      navigate('/persons');
    } catch (err) {
      setError(errMsg(err, 'Could not archive record'));
    }
  };

  if (error && !person) return <div className="error">{error}</div>;
  if (!person) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <div className="toolbar">
        <h1 style={{ margin: 0, marginRight: 'auto' }}>{person.full_name}</h1>
        {(user?.role !== 'NGO_WORKER') && (
          <Link className="btn btn-secondary" to={`/persons/${id}/edit`}>Edit</Link>
        )}
        {(user?.role !== 'CITIZEN' || person.created_by === user?.id) && user?.role !== 'NGO_WORKER' && (
          <button className="btn btn-ghost" onClick={remove}>Archive</button>
        )}
      </div>
      {error && <div className="error">{error}</div>}
      {msg && <div className="success">{msg}</div>}
      <div className="grid grid-2">
        <div className="card">
          <h3>Details</h3>
          <p><strong>Status:</strong> <span className={`badge badge-${person.status.toLowerCase()}`}>{person.status}</span></p>
          <p><strong>Age:</strong> {person.age ?? '—'} · <strong>Gender:</strong> {person.gender} · <strong>Height:</strong> {person.height_cm ? `${person.height_cm} cm` : '—'}</p>
          <p><strong>Last seen:</strong> {person.last_seen_location || '—'}{person.last_seen_city ? `, ${person.last_seen_city}` : ''}{person.last_seen_state ? `, ${person.last_seen_state}` : ''}</p>
          <p><strong>Date last seen:</strong> {person.date_last_seen || '—'}</p>
          <p><strong>Description:</strong> {person.description || '—'}</p>
          <p><strong>Contact:</strong> {person.contact_name || '—'} {person.contact_phone || ''} {person.contact_email || ''}</p>
        </div>
        <div className="card">
          <h3>Reference Photographs ({person.images?.length || 0})</h3>
          <div className="thumbs">
            {(person.images || []).map((img) => (
              <figure key={img.id} style={{ margin: 0 }}>
                <img src={img.url} alt="reference" title={img.is_primary ? 'Primary photo' : ''} />
                <figcaption className="muted" style={{ fontSize: '0.75rem' }}>
                  {isPoliceOrAdmin && img.ai_labels && (img.ai_labels.cnn || img.ai_labels.arcface)
                    ? `AI: ${[img.ai_labels.cnn && `CNN ${img.ai_labels.cnn}`, img.ai_labels.arcface && `ArcFace ${img.ai_labels.arcface}`].filter(Boolean).join(' · ')}`
                    : isPoliceOrAdmin ? 'AI: untagged' : ''}
                </figcaption>
              </figure>
            ))}
            {(person.images || []).length === 0 && <p className="muted">No photos yet.</p>}
          </div>
          <div className="toolbar" style={{ marginTop: '1rem' }}>
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(e) => setFiles(e.target.files)} />
            <button className="btn btn-primary" disabled={uploading || !files.length} onClick={upload}>{uploading ? 'Uploading…' : 'Upload'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}
