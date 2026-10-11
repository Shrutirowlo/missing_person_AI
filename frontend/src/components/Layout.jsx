import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

function CitizenNav() {
  return (
    <>
      <NavLink to="/dashboard">Dashboard</NavLink>
      <NavLink to="/persons">My Reports</NavLink>
      <NavLink to="/profile">Profile</NavLink>
    </>
  );
}

function PoliceNav() {
  return (
    <>
      <NavLink to="/dashboard">Dashboard</NavLink>
      <NavLink to="/persons">Missing-Person Reports</NavLink>
      <NavLink to="/dataset">Registered Persons</NavLink>
      <NavLink to="/search">AI Recognition Search</NavLink>
      <NavLink to="/history">Investigation History</NavLink>
      <NavLink to="/profile">Profile</NavLink>
    </>
  );
}

function AdminNav() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <NavLink to="/dashboard">Dashboard</NavLink>
      <NavLink to="/dataset">Registered Persons</NavLink>
      <NavLink to="/search">AI Recognition Search</NavLink>
      <NavLink to="/history">Investigation History</NavLink>
      <div className="nav-drop">
        <button
          type="button"
          className="nav-drop-btn"
          aria-expanded={open}
          aria-haspopup="true"
          onClick={() => setOpen((v) => !v)}
          onBlur={(e) => { if (!e.currentTarget.parentElement.contains(e.relatedTarget)) setOpen(false); }}
        >
          Admin ▾
        </button>
        {open && (
          <div className="nav-drop-menu" onClick={() => setOpen(false)}>
            <NavLink to="/admin/users">User Management</NavLink>
            <NavLink to="/admin/approvals">Police Approvals</NavLink>
            <NavLink to="/admin/dataset">Dataset Management</NavLink>
          </div>
        )}
      </div>
      <NavLink to="/profile">Profile</NavLink>
    </>
  );
}

function NGONav() {
  return (
    <>
      <NavLink to="/dashboard">Dashboard</NavLink>
      <NavLink to="/ngo/cases">Assigned Cases</NavLink>
      <NavLink to="/ngo/shared">Shared Cases</NavLink>
      <NavLink to="/ngo/sighting">Submit Sighting</NavLink>
      <NavLink to="/ngo/activity">My Activity</NavLink>
      <NavLink to="/profile">Profile</NavLink>
    </>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate('/login');
  };

  const NavItems = !user ? null
    : user.role === 'ADMIN' ? AdminNav
    : user.role === 'POLICE' ? PoliceNav
    : user.role === 'NGO_WORKER' ? NGONav
    : CitizenNav;

  return (
    <div className="app">
      <header className="topbar">
        <Link to={user ? '/dashboard' : '/'} className="brand">
          <span className="brand-mark">◉</span> Missing Person AI
        </Link>
        <nav className="nav">
          {user ? (
            <>
              {NavItems && <NavItems />}
              <span className="nav-user">{user.username} · {user.role}</span>
              <button className="btn btn-ghost" onClick={onLogout}>Logout</button>
            </>
          ) : (
            <>
              <NavLink to="/login">Login</NavLink>
              <NavLink to="/register" className="btn btn-primary">Register</NavLink>
            </>
          )}
        </nav>
      </header>
      <main className="content">{children}</main>
      <footer className="footer">AI-Powered Missing Person Identification · CNN · ArcFace · MediaPipe + KNN</footer>
    </div>
  );
}
