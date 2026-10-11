import api from './client';

export const listUsers = () => api.get('/admin/users');
export const changeRole = (userId, role) => api.patch(`/admin/users/${userId}/role`, { role });
export const setApproval = (userId, approved) => api.patch(`/admin/users/${userId}/approval`, { approved });
export const promoteAdmin = (userId) => api.post(`/admin/users/${userId}/promote-admin`);
