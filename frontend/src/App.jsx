import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import RoleRoute from './components/RoleRoute';
import { AuthProvider } from './context/AuthContext';
import AddMissingPerson from './pages/AddMissingPerson';
import AdminApprovals from './pages/AdminApprovals';
import AdminDataset from './pages/AdminDataset';
import AdminUsers from './pages/AdminUsers';
import Dashboard from './pages/Dashboard';
import DatasetPage from './pages/DatasetPage';
import EditMissingPerson from './pages/EditMissingPerson';
import Landing from './pages/Landing';
import Login from './pages/Login';
import MissingPersons from './pages/MissingPersons';
import NGOActivity from './pages/NGOActivity';
import NGOCases from './pages/NGOCases';
import PendingApproval from './pages/PendingApproval';
import PersonDetails from './pages/PersonDetails';
import Profile from './pages/Profile';
import Register from './pages/Register';
import Search from './pages/Search';
import SearchDetail from './pages/SearchDetail';
import SearchHistory from './pages/SearchHistory';
import SubmitSighting from './pages/SubmitSighting';
import Unauthorized from './pages/Unauthorized';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
          <Routes>
            {/* Public */}
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/unauthorized" element={<Unauthorized />} />
            <Route path="/pending-approval" element={<PendingApproval />} />

            {/* Any authenticated user */}
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            {/* Full report form: staff only (citizens report via photo upload) */}
            <Route path="/persons/new" element={
              <RoleRoute allowedRoles={['POLICE', 'ADMIN']}>
                <AddMissingPerson />
              </RoleRoute>
            } />
            <Route path="/persons/:id/edit" element={<ProtectedRoute><EditMissingPerson /></ProtectedRoute>} />
            <Route path="/persons/:id" element={<ProtectedRoute><PersonDetails /></ProtectedRoute>} />
            <Route path="/persons" element={<ProtectedRoute><MissingPersons /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />

            {/* History — all roles (backend strips sensitive data for restricted roles) */}
            <Route path="/history" element={
              <RoleRoute allowedRoles={['POLICE', 'ADMIN', 'CITIZEN', 'NGO_WORKER']}>
                <SearchHistory />
              </RoleRoute>
            } />
            <Route path="/history/:id" element={
              <RoleRoute allowedRoles={['POLICE', 'ADMIN', 'CITIZEN', 'NGO_WORKER']}>
                <SearchDetail />
              </RoleRoute>
            } />

            {/* Police + Admin only */}
            <Route path="/search" element={
              <RoleRoute allowedRoles={['POLICE', 'ADMIN']}>
                <Search />
              </RoleRoute>
            } />
            <Route path="/dataset" element={
              <RoleRoute allowedRoles={['POLICE', 'ADMIN']}>
                <DatasetPage />
              </RoleRoute>
            } />

            {/* Admin only */}
            <Route path="/admin/users" element={
              <RoleRoute allowedRoles={['ADMIN']}>
                <AdminUsers />
              </RoleRoute>
            } />
            <Route path="/admin/approvals" element={
              <RoleRoute allowedRoles={['ADMIN']}>
                <AdminApprovals />
              </RoleRoute>
            } />
            <Route path="/admin/dataset" element={
              <RoleRoute allowedRoles={['ADMIN']}>
                <AdminDataset />
              </RoleRoute>
            } />

            {/* NGO + Police + Admin */}
            <Route path="/ngo/cases" element={
              <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
                <NGOCases />
              </RoleRoute>
            } />
            <Route path="/ngo/shared" element={
              <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
                <NGOCases />
              </RoleRoute>
            } />
            <Route path="/ngo/sighting" element={
              <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
                <SubmitSighting />
              </RoleRoute>
            } />
            <Route path="/ngo/activity" element={
              <RoleRoute allowedRoles={['NGO_WORKER', 'POLICE', 'ADMIN']}>
                <NGOActivity />
              </RoleRoute>
            } />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </AuthProvider>
    </BrowserRouter>
  );
}
