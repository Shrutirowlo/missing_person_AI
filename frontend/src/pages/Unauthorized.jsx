import { Link } from 'react-router-dom';

export default function Unauthorized() {
  return (
    <div className="center-page">
      <h2>Access Denied</h2>
      <p className="muted">You do not have permission to view this page.</p>
      <Link to="/dashboard">← Back to Dashboard</Link>
    </div>
  );
}
