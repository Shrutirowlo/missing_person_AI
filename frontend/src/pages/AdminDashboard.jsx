import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';
import RecognitionPanel from '../components/RecognitionPanel';

export default function AdminDashboard() {
  const { user } = useAuth();
  const [pendingCount, setPendingCount] = useState(0);
  const [userCount, setUserCount] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/admin/users')
      .then((res) => {
        const users = res.data;
        setUserCount(users.length);
        setPendingCount(users.filter((u) => u.role === 'POLICE' && !u.approved).length);
      })
      .catch((err) => setError(errMsg(err, 'Could not load admin data')));
  }, []);

  return (
    <div>
      <h1>Admin Dashboard — {user?.first_name || user?.username}</h1>
      {error && <div className="error">{error}</div>}
      <div className="grid grid-3">
        <div className="card">
          <h3>Total Users</h3>
          <div className="score">{userCount}</div>
          <Link to="/admin/users">Manage users →</Link>
        </div>
        <div className="card">
          <h3>Pending Approvals</h3>
          <div className="score">{pendingCount}</div>
          <Link to="/admin/approvals">Review approvals →</Link>
        </div>
        <div className="card">
          <h3>Dataset Management</h3>
          <p className="muted">Import or update the registered-person dataset.</p>
          <Link to="/admin/dataset">Manage dataset →</Link>
        </div>
      </div>

      <h1 className="recognition-heading">AI-Powered Missing Person Identification System</h1>
      <p className="muted dashboard-sub">
        Admins can run the same three-model recognition as police officers.
      </p>
      <RecognitionPanel />

      <div className="grid grid-2">
        <div className="card">
          <h3>Registered Persons</h3>
          <p className="muted">Browse and manage registered-person records.</p>
          <Link to="/dataset">Open gallery →</Link>
        </div>
        <div className="card">
          <h3>System Administration</h3>
          <p className="muted">User roles, access control, and system settings.</p>
          <Link to="/admin/users">Open admin panel →</Link>
        </div>
      </div>
    </div>
  );
}
