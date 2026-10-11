import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 8 * 1024 * 1024;
const MAX_FILES = 10;

/** Citizen upload: person's name + one or more photographs.
 *  Creates a missing-person report and stores the photos with it in the
 *  database (missing_persons + person_images) — no long form to fill. */
export default function CitizenUploadPanel({ onUploaded }) {
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [thumbs, setThumbs] = useState([]); // [{ file, url, id }]
  const [busy, setBusy] = useState(false);
  const [validation, setValidation] = useState('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const acceptFiles = (list) => {
    setValidation('');
    setError('');
    setSaved(null);
    const incoming = Array.from(list || []);
    if (!incoming.length) return;
    const accepted = [];
    const problems = [];
    for (const f of incoming) {
      if (!ACCEPTED_TYPES.includes(f.type)) {
        problems.push(`${f.name}: unsupported file type (JPEG, PNG, or WebP only)`);
        continue;
      }
      if (f.size > MAX_BYTES) {
        problems.push(`${f.name}: too large (${(f.size / 1048576).toFixed(1)} MB, limit 8 MB)`);
        continue;
      }
      accepted.push({ file: f, url: URL.createObjectURL(f), id: `${f.name}-${f.size}-${Math.random().toString(36).slice(2)}` });
    }
    setThumbs((prev) => {
      const room = MAX_FILES - prev.length;
      if (accepted.length > room) problems.push(`Only ${room} more photo(s) allowed`);
      return [...prev, ...accepted.slice(0, Math.max(room, 0))];
    });
    if (problems.length) setValidation(problems.join(' · '));
  };

  const removeThumb = (id) => {
    setThumbs((prev) => {
      const t = prev.find((x) => x.id === id);
      if (t) URL.revokeObjectURL(t.url);
      return prev.filter((x) => x.id !== id);
    });
  };

  const save = async () => {
    if (busy) return;
    if (!name.trim()) {
      setValidation("Enter the missing person's name first.");
      return;
    }
    if (!thumbs.length) {
      setValidation('Attach at least one photograph.');
      return;
    }
    setBusy(true);
    setError('');
    setSaved(null);
    try {
      // 1. Create the report (minimal fields — no long form).
      const personRes = await api.post('/persons', {
        full_name: name.trim(),
        last_seen_location: location.trim(),
      });
      const person = personRes.data;
      // 2. Store the photographs with the report.
      const fd = new FormData();
      thumbs.forEach((t) => fd.append('files', t.file));
      await api.post(`/images/persons/${person.id}`, fd);
      thumbs.forEach((t) => URL.revokeObjectURL(t.url));
      setThumbs([]);
      setName('');
      setLocation('');
      setSaved(person);
      if (onUploaded) onUploaded(person);
    } catch (err) {
      setError(errMsg(err, 'Could not save your report'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Report by Photo Upload</h2>
      <p className="muted">
        Enter the person's name, attach their photograph, and submit — your report
        is stored and sent for review by authorized personnel.
      </p>
      {validation && <div className="error">{validation}</div>}
      {error && <div className="error">{error}</div>}
      {saved && (
        <div className="success-box">
          <strong>Report saved for “{saved.full_name}”</strong>
          {' '}<Link to={`/persons/${saved.id}`}>Open your report →</Link>
        </div>
      )}

      <input
        className="input"
        type="text"
        placeholder="Missing person's name"
        value={name}
        maxLength={200}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className="input"
        type="text"
        placeholder="Last seen location (optional)"
        value={location}
        maxLength={200}
        onChange={(e) => setLocation(e.target.value)}
      />

      <div
        className={`dropzone dropzone-multi${dragOver ? ' dropzone-over' : ''}${thumbs.length ? ' has-file' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); acceptFiles(e.dataTransfer?.files); }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
      >
        {thumbs.length ? (
          <div className="upload-thumbs">
            {thumbs.map((t) => (
              <figure key={t.id} className="upload-thumb">
                <img src={t.url} alt={t.file.name} />
                <button
                  type="button"
                  className="thumb-remove"
                  aria-label={`Remove ${t.file.name}`}
                  onClick={(e) => { e.stopPropagation(); removeThumb(t.id); }}
                >×</button>
                <figcaption className="muted">{t.file.name}</figcaption>
              </figure>
            ))}
            <div className="upload-more muted">+ drop more photos here<br />or click to add</div>
          </div>
        ) : (
          <>
            <p className="dropzone-icon">📷</p>
            <p><strong>Drag &amp; drop photograph(s) here</strong>, or click to browse</p>
            <p className="muted">JPEG, PNG, or WebP · up to 8 MB each · max {MAX_FILES}</p>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        style={{ display: 'none' }}
        onChange={(e) => { acceptFiles(e.target.files); e.target.value = ''; }}
      />

      <div className="toolbar">
        <button className="btn btn-primary" disabled={busy || !thumbs.length} onClick={save}>
          {busy ? 'Saving report…' : 'Submit Report'}
        </button>
      </div>
    </div>
  );
}
