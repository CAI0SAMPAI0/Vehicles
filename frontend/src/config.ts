export const API_BASE_URL = 
  (import.meta as any).env.VITE_API_URL || 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
