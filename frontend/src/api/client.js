import axios from 'axios';

const api = axios.create({ baseURL: '/api', timeout: 300000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('mp_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem('mp_token');
      localStorage.removeItem('mp_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

export const errMsg = (err, fallback = 'Request failed') =>
  err?.response?.data?.detail || err?.message || fallback;

export default api;
