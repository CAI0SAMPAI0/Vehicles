// Suporte a NEXT_API_BASE_URL (Vercel/Next), NEXT_PUBLIC_API_BASE_URL e VITE_API_URL (Vite)
const env = ((import.meta as any).env) || {};
const processEnv = typeof process !== 'undefined' && (process as any).env ? (process as any).env : {};

const envApiUrl: string | undefined = 
  env.NEXT_API_BASE_URL ||
  env.NEXT_PUBLIC_API_BASE_URL ||
  env.VITE_API_URL ||
  processEnv.NEXT_API_BASE_URL ||
  processEnv.NEXT_PUBLIC_API_BASE_URL ||
  processEnv.VITE_API_URL;

const rawBaseUrl = (envApiUrl && envApiUrl.trim() !== '')
  ? envApiUrl.trim()
  : (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
    ? 'http://127.0.0.1:8000'
    : 'https://api.example.com'; // Substitua pelo URL da sua API de produção

// Remove barra final para evitar URLs duplicadas tipo //api/v1/
export const API_BASE_URL: string = rawBaseUrl.replace(/\/+$/, '');
