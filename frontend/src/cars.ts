import { apiFetch } from './api';
import { API_BASE_URL } from './config';

interface Car {
    id: number;
    marca: string | null;
    modelo: string;
    ano: number | null;
    preco: number | null;
    foto: string | null;
    descricao: string | null;
    categoria: string | null;
}

// Labels de categoria em português
const CATEGORIA_LABELS: Record<string, string> = {
    SEDAN:     'Sedan',
    SUV:       'SUV',
    HATCH:     'Hatch',
    PICAPE:    'Picape',
    ESPORTIVO: 'Esportivo',
    MINIVAN:   'Minivan',
    ELETRICO:  'Elétrico',
    CLASSICO:  'Clássico',
    OUTRO:     'Outro',
};

// Cor do badge por categoria
const CATEGORIA_COLORS: Record<string, string> = {
    SEDAN:     'var(--text-dim)',
    SUV:       '#4a9eff',
    HATCH:     '#7a6fff',
    PICAPE:    '#d97706',
    ESPORTIVO: 'var(--red)',
    MINIVAN:   '#059669',
    ELETRICO:  '#10b981',
    CLASSICO:  'var(--gold)',
    OUTRO:     'var(--text-dim)',
};

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Checar se usuário está logado
    const username = localStorage.getItem('username');
    const authContainer = document.getElementById('auth-container');

    if (authContainer) {
        if (username) {
            authContainer.innerHTML = `
                <li class="nav-greeting">Olá, ${username}!</li>
                <li class="nav-btn-red"><a href="../new_car/">+ Cadastrar</a></li>
                <li><a href="../cars/">Garagem</a></li>
                <li><button id="logout-btn">Sair</button></li>
            `;
            document.getElementById('logout-btn')?.addEventListener('click', () => {
                localStorage.removeItem('username');
                localStorage.removeItem('auth_token');
                window.location.reload();
            });
        } else {
            authContainer.innerHTML = `
                <li><a href="../login/">Entrar</a></li>
                <li><a href="../register/">Cadastre-se</a></li>
            `;
        }
    }

    // 2. Elementos DOM
    const carsGrid       = document.getElementById('cars-grid');
    const searchInput    = document.getElementById('search-input')    as HTMLInputElement | null;
    const brandFilter    = document.getElementById('brand-filter')    as HTMLSelectElement | null;
    const categoryFilter = document.getElementById('category-filter') as HTMLSelectElement | null;
    const loadMoreBtn    = document.getElementById('load-more-btn')   as HTMLButtonElement | null;

    const ITEMS_PER_PAGE = 15;
    let currentPage = 1;
    let hasNextPage = true;
    let isLoading = false;
    let currentCarsList: Car[] = [];

    // ── Carregar marcas ──────────────────────────────────────────
    async function loadBrands() {
        if (!brandFilter) return;
        try {
            const brands = await apiFetch<{id: number, name: string}[]>('/api/v1/brands/');
            if (brands) {
                brandFilter.innerHTML = '<option value="">Todas as marcas</option>';
                brands.forEach(brand => {
                    const option = document.createElement('option');
                    option.value = brand.name;
                    option.textContent = brand.name;
                    brandFilter.appendChild(option);
                });
                const saved = sessionStorage.getItem('last_selected_brand');
                if (saved) brandFilter.value = saved;
            }
        } catch (err) {
            console.error('Erro ao buscar marcas:', err);
        }
    }

    // ── Carregar categorias ──────────────────────────────────────
    async function loadCategories() {
        if (!categoryFilter) return;
        try {
            const cats = await apiFetch<{value: string, label: string}[]>('/api/v1/categorias/');
            if (cats) {
                categoryFilter.innerHTML = '<option value="">Todas as categorias</option>';
                cats.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat.value;
                    option.textContent = cat.label;
                    categoryFilter.appendChild(option);
                });
                const saved = sessionStorage.getItem('last_selected_category');
                if (saved) categoryFilter.value = saved;
            }
        } catch (err) {
            console.error('Erro ao buscar categorias:', err);
        }
    }

    // ── Skeletons ────────────────────────────────────────────────
    function buildSkeletons(count: number, extraClass = '') {
        return Array(count).fill(0).map(() => `
            <div class="skeleton-card ${extraClass}">
                <div class="skeleton-img"></div>
                <div class="skeleton-body">
                    <div class="skeleton-line short"></div>
                    <div class="skeleton-line medium"></div>
                    <div style="overflow:hidden;margin-top:1.2rem;">
                        <div class="skeleton-line last"></div>
                        <div class="skeleton-line price"></div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // ── Carregar carros ──────────────────────────────────────────
    async function loadCars(reset = false) {
        if (isLoading) return;

        if (reset) {
            currentPage = 1;
            hasNextPage = true;
            currentCarsList = [];
            if (carsGrid) carsGrid.innerHTML = buildSkeletons(6);
        } else if (carsGrid) {
            const temp = document.createElement('div');
            temp.innerHTML = buildSkeletons(3, 'temp-skeleton');
            while (temp.firstChild) carsGrid.appendChild(temp.firstChild);
        }

        if (!hasNextPage) {
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());
            return;
        }

        isLoading = true;

        const query    = searchInput?.value.toLowerCase().trim() || '';
        const brand    = brandFilter?.value || '';
        const category = categoryFilter?.value || '';

        try {
            let url = `/api/v1/cars/?page=${currentPage}`;
            if (query)    url += `&search=${encodeURIComponent(query)}`;
            if (brand)    url += `&brand=${encodeURIComponent(brand)}`;
            if (category) url += `&categoria=${encodeURIComponent(category)}`;

            const response = await apiFetch<{ results: Car[], count: number, has_next: boolean }>(url);
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());

            if (response) {
                currentCarsList = [...currentCarsList, ...response.results];
                hasNextPage = response.has_next;
                renderCars(currentCarsList, response.count);
                currentPage++;
            }
        } catch (err) {
            console.error('Erro ao buscar carros:', err);
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());
            if (reset && carsGrid) {
                carsGrid.innerHTML = `
                    <div style="grid-column:span 3;width:100%;text-align:center;padding:3rem;">
                        <p style="color:var(--red);font-weight:600;">Erro ao carregar os carros do servidor.</p>
                    </div>
                `;
            }
        } finally {
            isLoading = false;
        }
    }

    // ── Renderizar carros ────────────────────────────────────────
    function renderCars(cars: Car[], totalCount: number) {
        if (!carsGrid) return;

        const carsMeta = document.getElementById('cars-meta');
        if (carsMeta) {
            const plural = totalCount === 1 ? 'veículo encontrado' : 'veículos encontrados';
            carsMeta.textContent = `${totalCount} ${plural}`;
        }

        if (cars.length === 0) {
            carsGrid.innerHTML = `
                <div class="empty-state" style="grid-column:span 3;width:100%;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <rect x="1" y="6" width="22" height="13" rx="2"/>
                        <path d="M5 6l2-3h10l2 3"/>
                        <circle cx="7.5" cy="13" r="1.5"/>
                        <circle cx="16.5" cy="13" r="1.5"/>
                    </svg>
                    <h3>Nenhum veículo encontrado</h3>
                    <p>Tente ajustar sua busca ou cadastre um novo carro.</p>
                </div>
            `;
            if (loadMoreBtn) loadMoreBtn.style.display = 'none';
            return;
        }

        carsGrid.innerHTML = cars.map((car, index) => {
            const fotoUrl = car.foto
                ? (car.foto.startsWith('http') ? car.foto : `${API_BASE_URL}${car.foto}`)
                : '';

            const precoFormatado = car.preco
                ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(car.preco)
                : 'Preço sob consulta';

            const indexString = (index + 1).toString().padStart(2, '0');

            const categoriaLabel = car.categoria ? (CATEGORIA_LABELS[car.categoria] || car.categoria) : null;
            const categoriaColor = car.categoria ? (CATEGORIA_COLORS[car.categoria] || 'var(--text-dim)') : null;
            const categoriaBadge = categoriaLabel
                ? `<span class="car-category-badge" style="color:${categoriaColor};border-color:${categoriaColor};">${categoriaLabel}</span>`
                : '';

            return `
                <a href="../car_detail/?id=${car.id}" class="car-link anim-fadeup" style="animation-delay:${(index % ITEMS_PER_PAGE) * 50}ms">
                    <div class="car-img">
                        <span class="car-index">${indexString}</span>
                        ${fotoUrl
                            ? `<img src="${fotoUrl}" alt="${car.modelo}" onError="this.style.display='none';this.nextElementSibling.style.display='flex';">`
                            : ''
                        }
                        <div class="no-photo" style="${fotoUrl ? 'display:none;' : ''}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
                                <rect x="1" y="6" width="22" height="13" rx="2"/>
                                <path d="M5 6l2-3h10l2 3"/>
                                <circle cx="7.5" cy="13" r="1.5"/>
                                <circle cx="16.5" cy="13" r="1.5"/>
                            </svg>
                            <span>Sem foto</span>
                        </div>
                    </div>
                    <div class="car-body">
                        <div class="car-brand-row">
                            <div class="car-brand">${car.marca || 'Marca não informada'}</div>
                            ${categoriaBadge}
                        </div>
                        <div class="car-name">${car.modelo}</div>
                        <div class="car-specs">
                            <span class="car-year">${car.ano || '-'}</span>
                            <span class="car-price">${precoFormatado}</span>
                        </div>
                    </div>
                </a>
            `;
        }).join('');

        if (loadMoreBtn) {
            loadMoreBtn.style.display = hasNextPage ? 'inline-block' : 'none';
        }
    }

    // ── Inicialização ────────────────────────────────────────────
    const savedQuery = sessionStorage.getItem('last_search_query');
    if (savedQuery && searchInput) searchInput.value = savedQuery;

    await Promise.all([loadBrands(), loadCategories()]);
    loadCars(true);

    // Debounce da busca
    let searchTimeout: number;
    searchInput?.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        if (searchInput) sessionStorage.setItem('last_search_query', searchInput.value);
        searchTimeout = window.setTimeout(() => loadCars(true), 400);
    });

    brandFilter?.addEventListener('change', () => {
        if (brandFilter) sessionStorage.setItem('last_selected_brand', brandFilter.value);
        loadCars(true);
    });

    categoryFilter?.addEventListener('change', () => {
        if (categoryFilter) sessionStorage.setItem('last_selected_category', categoryFilter.value);
        loadCars(true);
    });

    loadMoreBtn?.addEventListener('click', () => loadCars(false));

    window.addEventListener('scroll', () => {
        if (!loadMoreBtn || loadMoreBtn.style.display === 'none' || isLoading) return;
        const rect = loadMoreBtn.getBoundingClientRect();
        if (rect.top <= window.innerHeight + 200) loadCars(false);
    });
});
