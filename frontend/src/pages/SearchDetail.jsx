import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import DatasetThumb from '../components/DatasetThumb';
import GalleryPhotoStrip from '../components/GalleryPhotoStrip';
import ReportMatchBox from '../components/ReportMatchBox';

export default function SearchDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [search, setSearch] = useState(null);
  const [error, setError] = useState('');
  const isPoliceOrAdmin = ['POLICE', 'ADMIN'].includes(user?.role);

  useEffect(() => {
    api.get(`/search-history/${id}`)
      .then((res) => setSearch(res.data))
      .catch((err) => setError(errMsg(err, 'Could not load search')));
  }, [id]);

  if (error) return <div className="error">{error}</div>;
  if (!search) return <div className="center-page">Loading…</div>;

  return (
    <div>
      <h1>Recognition Result</h1>
      <p className="muted">Searched model: {search.model} · {search.created_at ? new Date(search.created_at).toLocaleString() : ''}</p>
      {search.query_image_url && <div className="preview"><img src={search.query_image_url} alt="query" /></div>}
      {isPoliceOrAdmin && <ReportMatchBox match={search.report_match} />}
      <div className="result-grid" style={{ marginTop: '1rem' }}>
        {Object.entries(search.results || {}).map(([name, r]) => (
          <div className="card" key={name}>
            <h3>{name}</h3>
            {!r.available && <><span className="badge badge-unavailable">Unavailable</span><p className="muted">{r.error}</p></>}
            {r.available && (
              <>
                {r.match_found ? <span className="badge badge-match">Registered match</span> : <span className="badge badge-nomatch">{r.status === 'no_reliable_match' ? 'No reliable match' : r.status}</span>}
                {isPoliceOrAdmin && <p><strong>Model prediction:</strong> {r.predicted_label || '—'}</p>}
                {isPoliceOrAdmin && r.match_found && r.registered_match ? (
                  <>
                    <p><strong>Registered gallery match:</strong> {r.registered_match}{' '}
                        <span className="muted">({r.detail?.gallery_image_count ?? '?'} photos in registered dataset)</span></p>
                    {r.registered_person_id && (
                      <p><strong>Registered record:</strong> <span className="muted">{r.registered_person_id}</span></p>
                    )}
                    {(r.source_photo_url || r.detail?.gallery_image_url) && (
                      <div className="thumbs">
                        <DatasetThumb srcUrl={r.source_photo_url || r.detail.gallery_image_url} label={r.registered_match} similarity="gallery photo" />
                      </div>
                    )}
                  </>
                ) : isPoliceOrAdmin ? (
                  <p className="muted"><strong>Registered gallery match:</strong> none — no reliable registered match.</p>
                ) : null}
                {!isPoliceOrAdmin && r.explanation && (
                  <p className="muted">{r.explanation}</p>
                )}
                {isPoliceOrAdmin && r.similarity != null && <p><strong>Similarity:</strong> {r.similarity}</p>}
                {isPoliceOrAdmin && r.confidence != null && <p><strong>Confidence:</strong> {(r.confidence * 100).toFixed(2)}%</p>}
                {isPoliceOrAdmin && r.explanation && <p className="muted"><strong>Why:</strong> {r.explanation}</p>}
                {isPoliceOrAdmin && r.detail?.matched_person_name && (
                  <p><strong>Also linked to your missing-person record:</strong> {r.detail.matched_person_name}{' '}
                    <span className="muted">(via {r.detail.matched_via === 'reference_photo' ? 'reference photo' : 'name'})</span></p>
                )}
                {r.person_id && <p><Link to={`/persons/${r.person_id}`}>Open missing-person record →</Link></p>}
                {isPoliceOrAdmin && r.detail?.top_images?.length > 0 && (
                  <details><summary>Dataset matches (CNN gallery)</summary>
                    <ul>{r.detail.top_images.slice(0, 10).map((t) => <li key={t.rank}>#{t.rank} {t.label} — {t.similarity}</li>)}</ul>
                  </details>
                )}
                {isPoliceOrAdmin && (
                  <GalleryPhotoStrip
                    title="Top matches with photos (CNN gallery)"
                    note="Only matches that resolve to a real stored photo are shown."
                    items={(r.detail?.top_images || []).filter((t) => t.photo_url).map((t) => ({
                      url: t.photo_url, label: t.label, similarity: t.similarity,
                    }))}
                  />
                )}
                {isPoliceOrAdmin && (
                  <GalleryPhotoStrip
                    title={`Gallery photos of predicted identity '${r.registered_match || r.predicted_label}'`}
                    note="Actual folder photos for visual comparison — not ranked per-photo matches."
                    items={(r.detail?.gallery_identity_photos || []).map((p) => ({
                      url: p.url, label: r.registered_match || r.predicted_label, similarity: 'gallery photo',
                    }))}
                  />
                )}
                {isPoliceOrAdmin && r.detail?.top_matches?.length > 0 && (
                  <details open><summary>Dataset matches (ArcFace gallery)</summary>
                    <div className="thumbs">
                      {r.detail.top_matches.slice(0, 10).map((t) => (
                        <DatasetThumb key={t.photo_id} photoId={t.photo_id} label={t.label} similarity={t.similarity} />
                      ))}
                    </div>
                  </details>
                )}
              </>
            )}
          </div>
        ))}
      </div>
      <p><Link to="/history">← Back to history</Link></p>
    </div>
  );
}
