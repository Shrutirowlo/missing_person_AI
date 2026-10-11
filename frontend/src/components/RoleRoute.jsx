import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * RoleRoute({ allowedRoles: string[], children })
 * Renders children only if user.role is in allowedRoles.
 * Redirects to /pending-approval if police account is not yet approved.
 * Redirects to /unauthorized otherwise.
 */
export default function RoleRoute({ allowedRoles, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="center-page">Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;

  if (user.role === 'POLICE' && !user.approved && allowedRoles.includes('POLICE')) {
    return <Navigate to="/pending-approval" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}
