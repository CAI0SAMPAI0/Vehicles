import { API_BASE_URL } from './config';

export async function apiFetch<T = any>(endpoint: string, options: RequestInit = {}): Promise<T | null> {
    const token = localStorage.getItem('auth_token');
    
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
    };
    
    if (token) {
        headers['Authorization'] = `Token ${token}`; 
    }
    
    const config: RequestInit = {
        ...options,
        headers,
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
        
        if (response.status === 401) {
            const refreshToken = localStorage.getItem('refresh_token');
            if (refreshToken) {
                try {
                    const refreshResponse = await fetch(`${API_BASE_URL}/api/v1/token/refresh/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ refresh_token: refreshToken })
                    });
                    if (refreshResponse.ok) {
                        const refreshData = await refreshResponse.json();
                        if (refreshData && refreshData.token) {
                            localStorage.setItem('auth_token', refreshData.token);
                            if (refreshData.refresh_token) {
                                localStorage.setItem('refresh_token', refreshData.refresh_token);
                            }
                            headers['Authorization'] = `Token ${refreshData.token}`;
                            const retryResponse = await fetch(`${API_BASE_URL}${endpoint}`, {
                                ...options,
                                headers
                            });
                            if (retryResponse.ok) {
                                return await retryResponse.json();
                            }
                        }
                    }
                } catch (refreshErr) {
                    console.error('Erro ao renovar token:', refreshErr);
                }
            }
            
            localStorage.removeItem('auth_token');
            localStorage.removeItem('refresh_token');
            // Só redireciona se não estivermos já na página de login
            if (!window.location.pathname.includes('login')) {
                window.location.href = '../login/';
            }
            return null;
        }
        
        if (!response.ok) {
            const contentType = response.headers.get('content-type') || '';
            let errorData: any = {};
            if (contentType.includes('application/json')) {
                errorData = await response.json().catch(() => ({}));
            }
            throw new Error(errorData.detail || errorData.error || `Erro ${response.status}`);
        }
        
        if (response.status === 204) {
            return true as unknown as T;
        }
        
        return await response.json();
    } catch (error: any) {
        console.error('API Fetch Error:', error);
        throw error;
    }
}

// Clear search filters when clicking the logo
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.nav-logo').forEach(logo => {
            logo.addEventListener('click', () => {
                sessionStorage.removeItem('last_search_query');
                sessionStorage.removeItem('last_selected_brand');
                sessionStorage.removeItem('last_selected_category');
            });
        });
    });
}

// Registro do Service Worker para PWA
if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(reg => {
                reg.update();
                console.log('Service Worker registrado com sucesso! Escopo:', reg.scope);
            })
            .catch(err => console.error('Erro ao registrar o Service Worker:', err));
    });
}

