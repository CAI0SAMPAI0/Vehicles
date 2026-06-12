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

    let allCars: Car[] = [];

    // Carregar carros
    try {
        const carsData = await apiFetch<Car[]>('/api/v1/cars/');
        if (carsData) {
            allCars = carsData;
            renderCars(allCars);
            populateBrandFilter(allCars);
        }
    } catch (err) {
        console.error('Erro ao buscar carros:', err);
        if (carsGrid) {
            carsGrid.innerHTML = `
                <div class="col-span-full text-center py-12">
                    <p class="text-brand-red font-semibold">Erro ao carregar os carros do servidor. Verifique a conexão.</p>
                </div>
            `;
        }
    }

    // Renderizar carros no grid
    function renderCars(cars: Car[]) {
        if (!carsGrid) return;
        
        // Atualizar contador de veículos encontrados
        const carsMeta = document.getElementById('cars-meta');
        if (carsMeta) {
            const count = cars.length;
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
            return;
        }

        carsGrid.innerHTML = cars.map((car, index) => {
            const fotoUrl = car.foto ? `${API_BASE_URL}${car.foto}` : '';
            const precoFormatado = car.preco 
                ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(car.preco)
                : 'Preço sob consulta';

            const indexString = (index + 1).toString().padStart(2, '0');

            return `
                <a href="../car_detail/?id=${car.id}" class="car-link anim-fadeup" style="animation-delay: ${index}00ms">
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
    }


    // Preencher filtro de marcas dinamicamente
    function populateBrandFilter(cars: Car[]) {
        if (!brandFilter) return;

        const brands = new Set<string>();
        cars.forEach(car => {
            if (car.marca) brands.add(car.marca);
        });

        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            option.className = 'bg-brand-panel';
            brandFilter.appendChild(option);
        });
    }

    // Filtrar carros por pesquisa e marca
    function filterAndRender() {
        const query = searchInput?.value.toLowerCase().trim() || '';
        const selectedBrand = brandFilter?.value || '';

        const filtered = allCars.filter(car => {
            const matchesSearch = car.modelo.toLowerCase().includes(query) || 
                                 (car.marca && car.marca.toLowerCase().includes(query)) ||
                                 (car.descricao && car.descricao.toLowerCase().includes(query));
            const matchesBrand = selectedBrand === '' || car.marca === selectedBrand;
            return matchesSearch && matchesBrand;
        });

        renderCars(filtered);
    }

    searchInput?.addEventListener('input', filterAndRender);
    brandFilter?.addEventListener('change', filterAndRender);
});
