// Suporte a NEXT_API_BASE_URL (Vercel/Next), NEXT_PUBLIC_API_BASE_URL e VITE_API_URL (Vite)
const metaEnv = (import.meta as any).env || {};
const globalEnv = (typeof globalThis !== 'undefined' && (globalThis as any).process?.env) || {};

const envApiUrl: string | undefined = 
  metaEnv.NEXT_API_BASE_URL ||
  metaEnv.NEXT_PUBLIC_API_BASE_URL ||
  metaEnv.VITE_API_URL ||
  globalEnv.NEXT_API_BASE_URL ||
  globalEnv.NEXT_PUBLIC_API_BASE_URL ||
  globalEnv.VITE_API_URL;

const rawBaseUrl = (envApiUrl && typeof envApiUrl === 'string' && envApiUrl.trim() !== '')
  ? envApiUrl.trim()
  : (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
    ? 'http://127.0.0.1:8000'
    : 'https://carros-j99v.onrender.com';

// Remove barra final para evitar URLs duplicadas tipo //api/v1/
export const API_BASE_URL: string = rawBaseUrl.replace(/\/+$/, '');
