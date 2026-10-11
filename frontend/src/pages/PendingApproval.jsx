import { useAuth } from '../context/AuthContext';

export default function PendingApproval() {
  const { logout } = useAuth();
  return (
    <div className="center-page">
      <h2>Account Pending Approval</h2>
      <p className="muted">
        Your police account is awaiting administrator approval.
        You will be able to access the system once an administrator approves your account.
      </p>
      <button className="btn btn-ghost" onClick={logout}>Logout</button>
    </div>
  );
}
