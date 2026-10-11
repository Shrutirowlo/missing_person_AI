import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errMsg } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function NGODashboard() {
  const { user } = useAuth();
  const [caseCount, setCaseCount] = useState(0);
  const [activityCount, setActivityCount] = useState(0);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [cases, activity] = await Promise.all([
          api.get('/ngo/cases'),
          api.get('/ngo/activity'),
        ]);
        setCaseCount(cases.data.length);
        setActivityCount(activity.data.length);
      } catch (err) {
        setError(errMsg(err, 'Could not load dashboard'));
      }
    })();
  }, []);

  return (
    <div>
      <h1>NGO Dashboard — {user?.first_name || user?.username}</h1>
      {user?.ngo_org && <p className="muted">Organisation: {user.ngo_org}</p>}
      {error && <div className="error">{error}</div>}
      <div className="grid grid-3">
        <div className="card">
          <h3>Assigned Cases</h3>
          <div className="score">{caseCount}</div>
          <Link to="/ngo/cases">View cases →</Link>
        </div>
        <div className="card">
          <h3>My Activity</h3>
          <div className="score">{activityCount}</div>
          <Link to="/ngo/activity">View activity →</Link>
        </div>
        <div className="card">
          <h3>Submit Sighting</h3>
          <p className="muted">Report a field observation or sighting.</p>
          <Link className="btn btn-primary" to="/ngo/sighting">Submit →</Link>
        </div>
      </div>
      <div className="card">
        <p className="muted">
          You can view cases shared with your NGO organisation and submit sightings or assistance
          updates. Police-only investigation details and identity recognition results are not
          accessible from this interface.
        </p>
      </div>
    </div>
  );
}
