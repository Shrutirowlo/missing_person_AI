import { Link } from 'react-router-dom';

/** Staff-only box: closest stored field-report photo to the query image.
 *  Rendered from result.report_match (search) or search.report_match
 *  (history detail). Similarity is shown raw with a verify-visually note —
 *  this is a candidate, never a proven identity. */
export default function ReportMatchBox({ match }) {
  if (!match) return null;
  return (
    <div className="report-match-box">
      <strong>Matching field report</strong>{' '}
      <span className="badge badge-match">Candidate</span>
      <p>
        <strong>{match.person_name}</strong>{' '}
        <span className="muted">
          (embedding similarity {(match.similarity * 100).toFixed(1)}% via{' '}
          {match.model === 'cnn' ? 'CNN' : match.model === 'arcface' ? 'ArcFace' : match.model})
        </span>
      </p>
      <p className="muted">{match.note || 'Verify visually — not a proven identity.'}</p>
      {match.person_id && (
        <p><Link to={`/persons/${match.person_id}`}>Open field report →</Link></p>
      )}
    </div>
  );
}
