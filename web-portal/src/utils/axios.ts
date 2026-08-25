import axios from 'axios';
import { message } from 'antd';

const api = axios.create({
  baseURL: '/api/v1',
});

let last403Message = 0;

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    } else if (error.response?.status === 403) {
      const headers = error.config?.headers as any;
      const isSilent = headers?.['X-Silent-Error'] === 'true' || headers?.['x-silent-error'] === 'true' || (typeof headers?.get === 'function' && headers.get('X-Silent-Error') === 'true');
      if (!isSilent) {
        const now = Date.now();
        if (now - last403Message > 2000) {
          message.error('You do not have permission to access this resource');
          last403Message = now;
        }
      }
    }
    return Promise.reject(error);
  }
);

// --- Simple API Caching Layer for Non-Sensitive Data ---
const cache = new Map<string, { response: any; expiry: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

// List of endpoints safe to cache (non-sensitive & rarely changing)
const CACHEABLE_ENDPOINTS = ['/roles', '/permissions'];

const originalGet = api.get;
// @ts-ignore
api.get = async (url: string, config?: any) => {
  const isCacheable = CACHEABLE_ENDPOINTS.includes(url);
  
  if (isCacheable) {
    const cached = cache.get(url);
    if (cached && cached.expiry > Date.now()) {
      return Promise.resolve(cached.response);
    }
  }

  const response = await originalGet.call(api, url, config);
  
  // @ts-ignore
  if (isCacheable && response?.data?.success) {
    cache.set(url, { response, expiry: Date.now() + CACHE_TTL });
  }
  
  return response;
};

// Invalidate cache on mutations
const invalidateCache = (url: string) => {
  if (url.startsWith('/roles')) cache.delete('/roles');
  if (url.startsWith('/permissions')) cache.delete('/permissions');
};

const originalPost = api.post;
// @ts-ignore
api.post = async (url: string, data?: any, config?: any) => {
  invalidateCache(url);
  return originalPost.call(api, url, data, config);
};

const originalPut = api.put;
// @ts-ignore
api.put = async (url: string, data?: any, config?: any) => {
  invalidateCache(url);
  return originalPut.call(api, url, data, config);
};

const originalDelete = api.delete;
// @ts-ignore
api.delete = async (url: string, config?: any) => {
  invalidateCache(url);
  return originalDelete.call(api, url, config);
};

export default api;
