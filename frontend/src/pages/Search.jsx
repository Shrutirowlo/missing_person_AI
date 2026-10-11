import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import DatasetThumb from '../components/DatasetThumb';
import GalleryPhotoStrip from '../components/GalleryPhotoStrip';
import ReportMatchBox from '../components/ReportMatchBox';

const MODEL_OPTIONS = [
  { value: 'all', label: 'All Models' },
  { value: 'cnn', label: 'CNN' },
  { value: 'arcface', label: 'ArcFace' },
  { value: 'mediapipe_knn', label: 'MediaPipe + KNN' },
];

function ResultCard({ name, result }) {
  if (!result) return null;
  if (!result.available) {
    return (
      <div className="card">
        <h3>{name}</h3>
        <span className="badge badge-unavailable">Unavailable</span>
        <p className="muted">{result.error}</p>
      </div>
    );
  }
  return (
    <div className="card">
      <h3>{name}</h3>
      {result.match_found
        ? <span className="badge badge-match">Registered match</span>
        : <span className="badge badge-nomatch">{result.status === 'no_reliable_match' ? 'No reliable match' : result.status}</span>}
      <p><strong>Model prediction:</strong> {result.predicted_label || '—'}</p>
      {result.match_found && result.registered_match ? (
        <>
          <p><strong>Registered gallery match:</strong> {result.registered_match}{' '}
              <span className="muted">({result.detail?.gallery_image_count ?? '?'} photos in registered dataset)</span></p>
          {result.registered_person_id && (
            <p><strong>Registered record:</strong> <span className="muted">{result.registered_person_id}</span></p>
          )}
          {(result.source_photo_url || result.detail?.gallery_image_url) && (
            <div className="thumbs">
              <DatasetThumb srcUrl={result.source_photo_url || result.detail.gallery_image_url} label={result.registered_match} similarity={`gallery photo`} />
            </div>
          )}
        </>
      ) : (
        <p className="muted"><strong>Registered gallery match:</strong> none — no reliable registered match.</p>
      )}
      {result.similarity != null && <p><strong>Similarity:</strong> <span className="score">{result.similarity}</span></p>}
      {result.confidence != null && <p><strong>Confidence:</strong> {(result.confidence * 100).toFixed(2)}%</p>}
      {result.explanation && <p className="muted"><strong>Why:</strong> {result.explanation}</p>}
      {result.detail?.matched_person_name && (
        <p><strong>Also linked to your missing-person record:</strong> {result.detail.matched_person_name}{' '}
          <span className="muted">(via {result.detail.matched_via === 'reference_photo' ? 'reference photo' : 'name'})</span></p>
      )}
      {result.person_id && (
        <p><Link to={`/persons/${result.person_id}`}>Open missing-person record →</Link></p>
      )}
      {result.detail?.top_classes?.length > 0 && (
        <details><summary>Top candidates (model output)</summary>
          <ul>{result.detail.top_classes.slice(0, 5).map((c) => <li key={c.label}>{c.label} — {c.score}</li>)}</ul>
        </details>
      )}
      {result.detail?.top_images?.length > 0 && (
        <details open><summary>Dataset matches — closest training photos (CNN gallery)</summary>
          <ul>{result.detail.top_images.slice(0, 10).map((t) => <li key={t.rank}>#{t.rank} {t.label} — {t.similarity}</li>)}</ul>
          <p className="muted">The original CNN index stores label + similarity per photo (no source file per row).</p>
        </details>
      )}
      <GalleryPhotoStrip
        title="Top matches with photos (CNN gallery)"
        note="Only matches that resolve to a real stored photo are shown — original CNN training rows have no file mapping."
        items={(result.detail?.top_images || []).filter((t) => t.photo_url).map((t) => ({
          url: t.photo_url, label: t.label, similarity: t.similarity,
        }))}
      />
      <GalleryPhotoStrip
        title={`Gallery photos of predicted identity '${result.registered_match || result.predicted_label}'`}
        note="Actual folder photos for visual comparison — not ranked per-photo matches."
        items={(result.detail?.gallery_identity_photos || []).map((p) => ({
          url: p.url, label: result.registered_match || result.predicted_label, similarity: 'gallery photo',
        }))}
      />
      {result.detail?.top_matches?.length > 0 && (
        <details open><summary>Dataset matches — closest training photos (ArcFace gallery)</summary>
          <div className="thumbs">
            {result.detail.top_matches.slice(0, 10).map((t) => (
              <DatasetThumb key={t.photo_id} photoId={t.photo_id} label={t.label} similarity={t.similarity} />
            ))}
          </div>
        </details>
      )}
      {result.detail?.decision && <p className="muted">Model decision: {result.detail.decision}{result.detail.margin != null ? ` · margin ${result.detail.margin}` : ''}</p>}
    </div>
  );
}

export default function Search() {
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [model, setModel] = useState('all');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [availability, setAvailability] = useState(null);

  useEffect(() => {
    if (!['POLICE', 'ADMIN'].includes(user?.role)) return;
    api.get('/recognition/availability').then((r) => setAvailability(r.data)).catch(() => {});
  }, [user]);

  if (!['POLICE', 'ADMIN'].includes(user?.role)) {
    return (
      <div className="card">
        <h2>Recognition Search</h2>
        <p className="muted">AI recognition search is available to authorized personnel only.</p>
      </div>
    );
  }

  const onFile = (e) => {
    const f = e.target.files?.[0];
    setFile(f || null);
    setPreview(f ? URL.createObjectURL(f) : '');
  };

  const run = async () => {
    if (busy || !file) return; // guard against double-clicks / duplicate submits
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('image', file);
      fd.append('model', model);
      const res = await api.post('/recognition/search', fd);
      setResult(res.data);
    } catch (err) {
      setError(errMsg(err, 'Recognition failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Recognition Search</h1>
      <div className="card">
        {error && <div className="error">{error}</div>}
        <div className="toolbar">
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onFile} />
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {MODEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button className="btn btn-primary" disabled={busy || !file} onClick={run}>{busy ? 'Analyzing…' : 'Start Recognition'}</button>
        </div>
        {availability && !availability.mediapipe_knn?.available && (
          <div className="notice">MediaPipe + KNN is currently unavailable: {availability.mediapipe_knn.error} Other models are unaffected.</div>
        )}
        {preview && <div className="preview"><img src={preview} alt="query preview" /></div>}
      </div>
      {busy && <div className="center-page">Running original AI models… this can take a minute on first load.</div>}
      {result && (
        <div>
          <h2>Results <span className="muted" style={{ fontSize: '1rem' }}>({result.models_evaluated.join(', ')})</span></h2>
          {result.query_image_url && <p className="muted">Query stored: {result.query_image_url} · <Link to={`/history/${result.search_id}`}>Open saved search →</Link></p>}
          <ReportMatchBox match={result.report_match} />
          <div className="result-grid">
            {Object.entries(result.results).map(([name, r]) => <ResultCard key={name} name={name} result={r} />)}
          </div>
        </div>
      )}
    </div>
  );
}
