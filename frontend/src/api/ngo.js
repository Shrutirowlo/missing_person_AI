import api from './client';

export const listCases = () => api.get('/ngo/cases');
export const submitSighting = (payload) => api.post('/ngo/sightings', payload);
export const getActivity = () => api.get('/ngo/activity');
