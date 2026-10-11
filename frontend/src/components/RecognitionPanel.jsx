import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import DatasetThumb from './DatasetThumb';
import GalleryPhotoStrip from './GalleryPhotoStrip';
import ReportMatchBox from './ReportMatchBox';

const MODEL_LABELS = { cnn: 'CNN', arcface: 'ArcFace', mediapipe_knn: 'MediaPipe + KNN' };
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 8 * 1024 * 1024;

/** Status line per requirement: completed / no reliable match / unavailable. */
function StatusBadge({ result }) {
  if (!result.available) return <span className="badge badge-unavailable">Unavailable</span>;
  if (result.error) return <span className="badge badge-nomatch">Error</span>;
  if (result.match_found) return <span className="badge badge-match">Completed — registered match</span>;
  return <span className="badge badge-nomatch">Completed — no reliable match</span>;
}

function SimilarityLine({ result }) {
  const parts = [];
  if (result.similarity != null) parts.push(<span key="sim"><strong>Similarity:</strong> <span className="score-inline">{result.similarity}</span></span>);
  if (result.confidence != null) parts.push(<span key="conf"><strong>Confidence:</strong> <span className="score-inline">{(result.confidence * 100).toFixed(2)}%</span></span>);
  if (!parts.length) return null;
  return <p className="scores-line">{parts}</p>;
}

function ResultCard({ name, result }) {
  if (!result) return null;
  return (
    <div className="card result-card">
      <h3>{MODEL_LABELS[result.model] || name}</h3>
      <StatusBadge result={result} />
      {result.error && <p className="error-card">{result.error}</p>}
      {!result.error && (
        <>
          <p><strong>Predicted identity:</strong> {result.predicted_label || '—'}</p>
          {result.match_found && result.registered_match ? (
            <>
              <p><strong>Registered person:</strong> {result.registered_match}
                {result.registered_person_id && (
                  <span className="muted"> (record {result.registered_person_id})</span>
                )}
              </p>
              {result.source_photo_url && (
                <div className="thumbs">
                  <DatasetThumb srcUrl={result.source_photo_url}
                    label={result.registered_match}
                    similarity={`registered photo`} />
                </div>
              )}
            </>
          ) : (
            <p className="muted"><strong>Registered person:</strong> none — no verified identity mapping.</p>
          )}
          <SimilarityLine result={result} />
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
              <ul className="tight-list">
                {result.detail.top_classes.slice(0, 5).map((c) => (
                  <li key={c.label}>{c.label} — {c.score}</li>
                ))}
              </ul>
            </details>
          )}
          {result.detail?.top_images?.length > 0 && (
            <details><summary>Dataset matches — closest training photos (CNN gallery)</summary>
              <ul className="tight-list">
                {result.detail.top_images.slice(0, 10).map((t) => (
                  <li key={t.rank}>#{t.rank} {t.label} — {t.similarity}</li>
                ))}
              </ul>
              <p className="muted">The original CNN index stores label + similarity per photo (no source file per row).</p>
            </details>
          )}
          <GalleryPhotoStrip
            title={`Top matches with photos (${MODEL_LABELS[result.model]} gallery)`}
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
            <details><summary>Dataset matches — closest training photos ({MODEL_LABELS[result.model]} gallery)</summary>
              <div className="thumbs">
                {result.detail.top_matches.slice(0, 10).map((t) => (
                  <DatasetThumb key={t.rank} photoId={t.photo_id} model={result.model}
                    label={t.label} similarity={t.similarity} />
                ))}
              </div>
            </details>
          )}
          {result.detail?.neighbor_votes?.length > 0 && (
            <details><summary>KNN neighbor vote</summary>
              <ul className="tight-list">
                {result.detail.neighbor_votes.slice(0, 5).map((v) => (
                  <li key={v.label}>{v.label} — {v.votes}/{v.of} neighbors</li>
                ))}
              </ul>
            </details>
          )}
          {result.detail?.decision && (
            <p className="muted">Model decision: {result.detail.decision}
              {result.detail.margin != null ? ` · margin ${result.detail.margin}` : ''}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function RecognitionPanel() {
  const { user } = useAuth();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [validation, setValidation] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [result, setResult] = useState(null);
  const [availability, setAvailability] = useState(null);
  const [datasetSync, setDatasetSync] = useState(null);
  const inputRef = useRef(null);

  // Staff-only screen (rendered by Dashboard for POLICE/ADMIN only):
  // upload a photo and run all three models. The backend enforces the same
  // role check on /api/recognition/*.
  const canRun = Boolean(user);

  useEffect(() => {
    if (!canRun) return;
    api.get('/recognition/availability').then((r) => setAvailability(r.data)).catch(() => {});
    api.get('/dataset/registered')
      .then((r) => setDatasetSync(r.data))
      .catch(() => setDatasetSync({ imported: null }));
  }, [canRun]);

  if (!canRun) {
    return (
      <div className="card">
        <h2>AI Recognition</h2>
        <p className="muted">Please log in to upload a photograph and run all three models.</p>
      </div>
    );
  }

  const acceptFile = (f) => {
    setValidation('');
    setError('');
    setResult(null);
    if (!f) return;
    if (!ACCEPTED_TYPES.includes(f.type)) {
      setFile(null);
      setPreview('');
      setValidation('Unsupported file type. Please choose a JPEG, PNG, or WebP photograph.');
      return;
    }
    if (f.size > MAX_BYTES) {
      setFile(null);
      setPreview('');
      setValidation(`Image is too large (${(f.size / 1048576).toFixed(1)} MB). The limit is 8 MB.`);
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const onInputChange = (e) => acceptFile(e.target.files?.[0]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    acceptFile(e.dataTransfer?.files?.[0]);
  };

  const onDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const run = async () => {
    if (busy) return; // guard against double-clicks / duplicate submits
    if (!file) {
      setValidation('Select or drop a photograph first.');
      return;
    }
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('image', file);
      fd.append('model', 'all');
      const res = await api.post('/recognition/search', fd);
      setResult(res.data);
    } catch (err) {
      setError(errMsg(err, 'Recognition failed'));
    } finally {
      setBusy(false);
    }
  };

  const formatMs = (ms) => (ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`);

  const summaryClass = result?.summary
    ? result.summary.verdict === 'consistent' ? 'summary-box summary-consistent'
      : result.summary.verdict === 'conflicting' ? 'summary-box summary-conflicting'
        : 'summary-box summary-inconclusive'
    : null;

  return (
    <div>
      <div className="card">
        <h2>Upload Image for Recognition</h2>
        {validation && <div className="error">{validation}</div>}
        {error && <div className="error">{error}</div>}
        {datasetSync && datasetSync.imported === false && (
          <div className="notice">
            Registered-person records are not imported into the database yet, so model
            predictions cannot be linked to registered records. An admin can fix this
            from Dataset Management (Run import).
          </div>
        )}
        {availability && availability.mediapipe_knn && !availability.mediapipe_knn.available && (
          <div className="notice">
            MediaPipe + KNN is currently unavailable on this machine and will report
            its real error: {availability.mediapipe_knn.error} Other models are unaffected.
          </div>
        )}
        <div
          className={`dropzone${dragOver ? ' dropzone-over' : ''}${file ? ' has-file' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
        >
          {preview ? (
            <div className="dropzone-preview">
              <img src={preview} alt="Selected query preview" />
              <p className="muted">{file?.name} — click or drop another image to replace</p>
            </div>
          ) : (
            <>
              <p className="dropzone-icon">📷</p>
              <p><strong>Drag &amp; drop a photograph here</strong>, or click to browse</p>
              <p className="muted">JPEG, PNG, or WebP · up to 8 MB · faces of registered or missing persons</p>
            </>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={onInputChange}
        />
        <div className="toolbar">
          <button className="btn btn-primary btn-run" disabled={busy || !file} onClick={run}>
            {busy ? 'Running all three models…' : 'Run All Three Models'}
          </button>
          {file && !busy && (
            <button className="btn btn-ghost" onClick={() => acceptFile(null)}>Clear</button>
          )}
        </div>
        {busy && (
          <div className="running">
            <span className="spinner" aria-hidden="true"></span>
            Running the original CNN, ArcFace, and MediaPipe + KNN models… this can take a
            minute on first load while model artifacts are read.
          </div>
        )}
      </div>

      {result && (
        <div>
          <h2>Recognition Results</h2>
          {result.query_image_url && (
            <p className="muted">
              Query stored: {result.query_image_url} ·{' '}
              <Link to={`/history/${result.search_id}`}>Open saved search →</Link>
            </p>
          )}
          {result.summary && (
            <div className={summaryClass}>
              <strong>Combined summary ({result.summary.verdict}):</strong> {result.summary.message}
            </div>
          )}
          <ReportMatchBox match={result.report_match} />
          {result.summary?.timings && (
            <p className="muted timing-line">
              Per-model time: CNN {formatMs(result.summary.timings.cnn)} ·{' '}
              ArcFace {formatMs(result.summary.timings.arcface)} ·{' '}
              MediaPipe + KNN {formatMs(result.summary.timings.mediapipe_knn)}
              {' · '}total {formatMs(result.summary.total_elapsed_ms)}
            </p>
          )}
          <div className="result-grid">
            {['cnn', 'arcface', 'mediapipe_knn'].map((m) => (
              <ResultCard key={m} name={MODEL_LABELS[m]} result={result.results?.[m]} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
