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
}

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Checar se usuário está logado
    const username = localStorage.getItem('username');
    const authContainer = document.getElementById('auth-container');
    
    if (authContainer) {
        if (username) {
            authContainer.innerHTML = `
                <li class="text-brand-text-dim border-l-2 border-brand-red px-3.5 py-1.5">Olá, ${username}!</li>
                <li class="bg-brand-red text-white px-4 py-1.5 rounded-sm hover:bg-brand-red/80 transition-colors">
                    <a href="../new_car/">Cadastrar</a>
                </li>
                <li><a href="../cars/" class="text-brand-text-hi bg-brand-panel px-3.5 py-1.5 rounded-sm transition-all">Garagem</a></li>
                <li><button id="logout-btn" class="text-brand-text-dim hover:text-brand-text-hi hover:bg-brand-panel px-3.5 py-1.5 rounded-sm transition-all uppercase font-semibold">Sair</button></li>
            `;
            
            document.getElementById('logout-btn')?.addEventListener('click', () => {
                localStorage.removeItem('username');
                localStorage.removeItem('auth_token');
                window.location.reload();
            });
        } else {
            authContainer.innerHTML = `
                <li><a href="../login/" class="bg-brand-red text-white px-4 py-1.5 rounded-sm hover:bg-brand-red/80 transition-colors">Entrar</a></li>
                <li><a href="../register/" class="text-brand-text-dim hover:text-brand-text-hi hover:bg-brand-panel px-3.5 py-1.5 rounded-sm transition-all">Cadastre-se</a></li>
            `;
        }
    }

    // 2. Elementos DOM para a lista de carros
    const carsGrid = document.getElementById('cars-grid');
    const searchInput = document.getElementById('search-input') as HTMLInputElement | null;
    const brandFilter = document.getElementById('brand-filter') as HTMLSelectElement | null;
    const loadMoreBtn = document.getElementById('load-more-btn') as HTMLButtonElement | null;

    const ITEMS_PER_PAGE = 15;
    let currentPage = 1;
    let hasNextPage = true;
    let isLoading = false;
    let currentCarsList: Car[] = [];

    // Carregar marcas para o filtro inicial
    async function loadBrands() {
        if (!brandFilter) return;
        try {
            const brands = await apiFetch<{id: number, name: string}[]>('/api/v1/brands/');
            if (brands) {
                // Limpa opções anteriores mantendo a primeira vazia
                brandFilter.innerHTML = '<option value="">Filtrar por marca</option>';
                brands.forEach(brand => {
                    const option = document.createElement('option');
                    option.value = brand.name;
                    option.textContent = brand.name;
                    option.className = 'bg-brand-panel';
                    brandFilter.appendChild(option);
                });
                
                // Restaurar marca selecionada
                const savedBrand = sessionStorage.getItem('last_selected_brand');
                if (savedBrand) {
                    brandFilter.value = savedBrand;
                }
            }
        } catch (err) {
            console.error('Erro ao buscar marcas:', err);
        }
    }

    // Carregar página de carros
    async function loadCars(reset = false) {
        if (isLoading) return;
        if (reset) {
            currentPage = 1;
            hasNextPage = true;
            currentCarsList = [];
            if (carsGrid) {
                carsGrid.innerHTML = Array(6).fill(0).map(() => `
                    <div class="skeleton-card">
                        <div class="skeleton-img"></div>
                        <div class="skeleton-body">
                            <div class="skeleton-line short"></div>
                            <div class="skeleton-line medium"></div>
                            <div style="overflow: hidden; margin-top: 1.2rem;">
                                <div class="skeleton-line last"></div>
                                <div class="skeleton-line price"></div>
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        } else if (carsGrid) {
            // Append temporary skeletons at the bottom
            const tempContainer = document.createElement('div');
            tempContainer.innerHTML = Array(3).fill(0).map(() => `
                <div class="skeleton-card temp-skeleton">
                    <div class="skeleton-img"></div>
                    <div class="skeleton-body">
                        <div class="skeleton-line short"></div>
                        <div class="skeleton-line medium"></div>
                        <div style="overflow: hidden; margin-top: 1.2rem;">
                            <div class="skeleton-line last"></div>
                            <div class="skeleton-line price"></div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            while (tempContainer.firstChild) {
                carsGrid.appendChild(tempContainer.firstChild);
            }
        }
        
        if (!hasNextPage) {
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());
            return;
        }
        isLoading = true;

        const query = searchInput?.value.toLowerCase().trim() || '';
        const selectedBrand = brandFilter?.value || '';
        
        try {
            let url = `/api/v1/cars/?page=${currentPage}`;
            
            if (query) {
                url += `&search=${encodeURIComponent(query)}`;
            }
            if (selectedBrand) {
                url += `&brand=${encodeURIComponent(selectedBrand)}`;
            }
            
            const response = await apiFetch<{ results: Car[], count: number, has_next: boolean }>(url);
            
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());
            
            if (response) {
                const newCars = response.results;
                currentCarsList = [...currentCarsList, ...newCars];
                hasNextPage = response.has_next;
                
                renderCars(currentCarsList, response.count);
                currentPage++;
            }
        } catch (err) {
            console.error('Erro ao buscar carros:', err);
            document.querySelectorAll('.temp-skeleton').forEach(el => el.remove());
            if (reset && carsGrid) {
                carsGrid.innerHTML = `
                    <div class="col-span-full text-center py-12" style="grid-column: span 3; width: 100%;">
                        <p class="text-brand-red font-semibold" style="color: var(--red);">Erro ao carregar os carros do servidor.</p>
                    </div>
                `;
            }
        } finally {
            isLoading = false;
        }
    }

    // Renderizar carros no grid
    function renderCars(cars: Car[], totalCount: number) {
        if (!carsGrid) return;
        
        // Atualizar contador de veículos encontrados
        const carsMeta = document.getElementById('cars-meta');
        if (carsMeta) {
            const count = totalCount;
            const pluralVeiculo = count === 1 ? 'veículo encontrado' : 'veículos encontrados';
            carsMeta.textContent = `${count} ${pluralVeiculo}`;
        }

        if (cars.length === 0) {
            carsGrid.innerHTML = `
                <div class="empty-state" style="grid-col: span 3; width: 100%;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <rect x="1" y="6" width="22" height="13" rx="2"/><path d="M5 6l2-3h10l2 3"/><circle cx="7.5" cy="13" r="1.5"/><circle cx="16.5" cy="13" r="1.5"/>
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

            return `
                <a href="../car_detail/?id=${car.id}" class="car-link anim-fadeup" style="animation-delay: ${(index % ITEMS_PER_PAGE) * 50}ms">
                    <div class="car-img">
                        <span class="car-index">${indexString}</span>
                        ${fotoUrl 
                            ? `<img src="${fotoUrl}" alt="${car.modelo}" onError="this.style.display='none'; this.nextElementSibling.style.display='flex';">` 
                            : ''
                        }
                        <div class="no-photo" style="${fotoUrl ? 'display: none;' : ''}">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
                                <rect x="1" y="6" width="22" height="13" rx="2"/><path d="M5 6l2-3h10l2 3"/><circle cx="7.5" cy="13" r="1.5"/><circle cx="16.5" cy="13" r="1.5"/>
                            </svg>
                            <span>Sem foto</span>
                        </div>
                    </div>
                    <div class="car-body">
                        <div class="car-brand">${car.marca || 'Marca não informada'}</div>
                        <div class="car-name">${car.modelo}</div>
                        <div class="car-specs">
                            <span class="car-year">${car.ano || '-'}</span>
                            <span class="car-price">${precoFormatado}</span>
                        </div>
                    </div>
                </a>
            `;
        }).join('');

        // Exibe ou oculta o botão de carregar mais
        if (loadMoreBtn) {
            if (hasNextPage) {
                loadMoreBtn.style.display = 'inline-block';
            } else {
                loadMoreBtn.style.display = 'none';
            }
        }
    }

    // Inicialização
    const savedQuery = sessionStorage.getItem('last_search_query');
    if (savedQuery && searchInput) {
        searchInput.value = savedQuery;
    }
    
    await loadBrands();
    loadCars(true);

    // Debounce para evitar sobrecarga de requisições ao digitar
    let searchTimeout: number;
    searchInput?.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        if (searchInput) {
            sessionStorage.setItem('last_search_query', searchInput.value);
        }
        searchTimeout = window.setTimeout(() => {
            loadCars(true);
        }, 400);
    });

    brandFilter?.addEventListener('change', () => {
        if (brandFilter) {
            sessionStorage.setItem('last_selected_brand', brandFilter.value);
        }
        loadCars(true);
    });

    // Ações para o botão Carregar Mais
    loadMoreBtn?.addEventListener('click', () => {
        loadCars(false);
    });

    // Rolagem infinita (detecta proximidade do rodapé da tela para carregar mais)
    window.addEventListener('scroll', () => {
        if (!loadMoreBtn || loadMoreBtn.style.display === 'none' || isLoading) return;
        const rect = loadMoreBtn.getBoundingClientRect();
        if (rect.top <= window.innerHeight + 200) {
            loadCars(false);
        }
    });
});
