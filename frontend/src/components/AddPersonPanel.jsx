import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 8 * 1024 * 1024;
const MAX_FILES = 50;
const MODEL_LABELS = { cnn: 'CNN', arcface: 'ArcFace', mediapipe_knn: 'MediaPipe + KNN' };

const formatMs = (ms) => (ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`);

/** Dashboard section: upload one or more photos of a person and store them
 *  in the ORIGINAL registered dataset (data/registered/<identity>/). */
export default function AddPersonPanel() {
  const [name, setName] = useState('');
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
        problems.push(`${f.name}: unsupported type (JPEG, PNG, or WebP only)`);
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
      if (accepted.length > room) problems.push(`Only ${room} more photo(s) allowed per batch`);
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

  const clearAll = () => {
    thumbs.forEach((t) => URL.revokeObjectURL(t.url));
    setThumbs([]);
    setValidation('');
    setError('');
    setSaved(null);
  };

  const save = async () => {
    if (!name.trim()) {
      setValidation("Enter the person's name first.");
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
      const fd = new FormData();
      fd.append('name', name.trim());
      thumbs.forEach((t) => fd.append('files', t.file));
      const res = await api.post('/dataset/person', fd);
      setSaved(res.data);
      thumbs.forEach((t) => URL.revokeObjectURL(t.url));
      setThumbs([]);
      setName('');
    } catch (err) {
      setError(errMsg(err, 'Could not store the photos in the dataset'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h2>Add Person to Registered Dataset</h2>
      <p className="muted">
        Upload one or more photographs of a person — they are stored in the original
        registered dataset (one folder per identity) and linked in the database.
      </p>
      {validation && <div className="error">{validation}</div>}
      {error && <div className="error">{error}</div>}
      {saved && (
        <div className="success-box">
          <strong>Saved {saved.saved_count} photo(s) for “{saved.name}”</strong> → dataset
          folder <code>data/registered/{saved.identity}/</code>
          {saved.folder_photo_count != null && (
            <span> · {saved.folder_photo_count} photo(s) now in this identity</span>
          )}
          .{' '}
          {saved.gallery_url && <Link to="/dataset">Open registered gallery →</Link>}
          {saved.rejected?.length > 0 && (
            <div className="muted">
              Not stored: {saved.rejected.map((r) => `${r.filename} (${r.error})`).join('; ')}
            </div>
          )}
          {saved.index_report && (
            <div className="index-report">
              <strong>Model index update</strong> (original pipelines, artifacts untouched):
              <ul className="tight-list">
                {Object.entries(saved.index_report).map(([model, r]) => (
                  <li key={model}>
                    <strong>{MODEL_LABELS[model] || model}:</strong>{' '}
                    {r.status === 'updated' && (
                      <span className="badge badge-match">indexed</span>
                    )}
                    {r.status === 'no_change' && (
                      <span className="badge badge-nomatch">already indexed</span>
                    )}
                    {r.status === 'skipped' && (
                      <span className="badge badge-nomatch">skipped</span>
                    )}
                    {r.status === 'unavailable' && (
                      <span className="badge badge-unavailable">unavailable</span>
                    )}{' '}
                    <span className="muted">
                      {r.status === 'updated' && <>added {r.added} photo(s) in {formatMs(r.elapsed_ms)}</>}
                      {r.status === 'no_change' && <>no new photos in {formatMs(r.elapsed_ms)}</>}
                      {r.status === 'skipped' && r.reason}
                      {r.status === 'unavailable' && r.error}
                      {r.failed?.length > 0 && (
                        <> · could not embed: {r.failed.map((f) => f.file).join(', ')}</>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <span className="muted">
                This person is now searchable with the next recognition run.
              </span>
            </div>
          )}
        </div>
      )}

      <input
        className="input"
        type="text"
        placeholder="Person's name (e.g. John Doe)"
        value={name}
        maxLength={100}
        onChange={(e) => setName(e.target.value)}
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
            <p className="dropzone-icon">🖼️</p>
            <p><strong>Drag &amp; drop one or more photos here</strong>, or click to browse</p>
            <p className="muted">Multiple photos welcome · JPEG, PNG, or WebP · up to 8 MB each · max {MAX_FILES} per batch</p>
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
          {busy ? 'Storing in dataset…' : `Save ${thumbs.length || ''} to Dataset`}
        </button>
        {thumbs.length > 0 && !busy && (
          <button className="btn btn-ghost" onClick={clearAll}>Clear all</button>
        )}
      </div>
      {busy && (
        <div className="running">
          <span className="spinner" aria-hidden="true"></span>
          Storing photos into data/registered/, updating records, and embedding into
          the model indexes…
        </div>
      )}
    </div>
  );
}
