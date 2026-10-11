import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Landing() {
  const { user } = useAuth();
  return (
    <div className="hero">
      <h1>AI-Powered Missing Person Identification</h1>
      <p>
        Register missing persons, upload reference photographs, and run recognition
        across three independent AI approaches — CNN, ArcFace, and MediaPipe + KNN —
        with every result traceable to the model that produced it.
      </p>
      <div className="hero-actions">
        {user ? (
          <>
            <Link className="btn btn-primary" to="/dashboard">Go to Dashboard</Link>
            <Link className="btn btn-secondary" to="/search">Run a Search</Link>
          </>
        ) : (
          <>
            <Link className="btn btn-primary" to="/register">Create Account</Link>
            <Link className="btn btn-secondary" to="/login">Login</Link>
          </>
        )}
      </div>
      <div className="model-list" style={{ justifyContent: 'center' }}>
        <span className="model-pill">CNN · 128-D embeddings + KNN</span>
        <span className="model-pill">ArcFace · 512-D angular-margin</span>
        <span className="model-pill">MediaPipe + KNN · 478-point mesh</span>
      </div>
    </div>
  );
}
