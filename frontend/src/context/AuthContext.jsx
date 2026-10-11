import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('mp_user') || 'null');
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('mp_token');
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get('/auth/profile')
      .then((res) => {
        setUser(res.data);
        localStorage.setItem('mp_user', JSON.stringify(res.data));
      })
      .catch(() => {
        localStorage.removeItem('mp_token');
        localStorage.removeItem('mp_user');
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    localStorage.setItem('mp_token', res.data.access_token);
    localStorage.setItem('mp_user', JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const res = await api.post('/auth/register', payload);
    localStorage.setItem('mp_token', res.data.access_token);
    localStorage.setItem('mp_user', JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      /* stateless logout: ignore */
    }
    localStorage.removeItem('mp_token');
    localStorage.removeItem('mp_user');
    setUser(null);
  }, []);

  // Role helper functions
  const isAdmin = useCallback(() => user?.role === 'ADMIN', [user]);
  const isPolice = useCallback(() => user?.role === 'POLICE', [user]);
  const isCitizen = useCallback(() => user?.role === 'CITIZEN', [user]);
  const isNGO = useCallback(() => user?.role === 'NGO_WORKER', [user]);
  const isPoliceApproved = useCallback(() => user?.role === 'POLICE' && user?.approved === true, [user]);
  const isPoliceOrAdmin = useCallback(() => ['POLICE', 'ADMIN'].includes(user?.role), [user]);

  return (
    <AuthContext.Provider value={{
      user, loading, login, register, logout,
      isAdmin, isPolice, isCitizen, isNGO, isPoliceApproved, isPoliceOrAdmin,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
