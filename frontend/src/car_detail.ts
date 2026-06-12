import { apiFetch } from './api';
import { API_BASE_URL } from './config';

interface CarDetails {
    id: number;
    brand: number | null;
    marca: string | null;
    modelo: string;
    ano_fabricacao: number | null;
    ano_modelo: number | null;
    placa: string | null;
    preco: number | null;
    foto: string | null;
    descricao: string | null;
}

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Obter ID do carro da URL
    const urlParams = new URLSearchParams(window.location.search);
    const carId = urlParams.get('id');

    if (!carId) {
        alert('Carro não especificado.');
        window.location.href = '../cars/';
        return;
    }

    // 2. Elementos do DOM
    const photoContainer = document.getElementById('car-photo-container');
    const brandTag = document.getElementById('car-brand-tag');
    const modelTitle = document.getElementById('car-model-title');
    const valueDisplay = document.getElementById('car-value-display');
    const bioText = document.getElementById('car-bio');
    const specFactoryYear = document.getElementById('spec-factory-year');
    const specModelYear = document.getElementById('spec-model-year');
    const specPlate = document.getElementById('spec-plate');
    const btnEdit = document.getElementById('btn-edit');
    const btnDelete = document.getElementById('btn-delete');

    // 3. Buscar detalhes do carro
    try {
        const car = await apiFetch<CarDetails>(`/api/v1/car/${carId}/`);
        if (car) {
            renderCarDetails(car);
        } else {
            alert('Não foi possível encontrar os detalhes do carro.');
            window.location.href = '../cars/';
        }
    } catch (err) {
        console.error('Erro ao buscar detalhes do carro:', err);
        alert('Erro ao carregar detalhes do carro.');
        window.location.href = '../cars/';
    }

    // Função para renderizar os dados no DOM
    function renderCarDetails(car: CarDetails) {
        const fotoUrl = car.foto ? `${API_BASE_URL}${car.foto}` : '';
        const precoFormatado = car.preco 
            ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(car.preco)
            : 'Preço sob consulta';

        if (photoContainer) {
            if (fotoUrl) {
                photoContainer.innerHTML = `<img src="${fotoUrl}" alt="${car.modelo}">`;
            } else {
                photoContainer.innerHTML = `
                    <div class="no-photo-lg">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                            <rect x="1" y="6" width="22" height="13" rx="2"/><path d="M5 6l2-3h10l2 3"/><circle cx="7.5" cy="13" r="1.5"/><circle cx="16.5" cy="13" r="1.5"/>
                        </svg>
                        <span>Foto não disponível</span>
                    </div>
                `;
            }
        }

        if (brandTag) brandTag.textContent = car.marca || 'MARCA';
        if (modelTitle) modelTitle.textContent = car.modelo;
        if (valueDisplay) valueDisplay.textContent = precoFormatado;
        
        // Exibir bio se houver
        const bioCard = document.getElementById('car-bio-card');
        if (bioCard && bioText) {
            if (car.descricao) {
                bioText.textContent = car.descricao;
                bioCard.style.display = 'block';
            } else {
                bioCard.style.display = 'none';
            }
        }
        
        if (specFactoryYear) specFactoryYear.textContent = car.ano_fabricacao?.toString() || '—';
        if (specModelYear) specModelYear.textContent = car.ano_modelo?.toString() || '—';
        if (specPlate) specPlate.textContent = car.placa || '—';

        // Mostrar ações apenas se o usuário estiver logado
        const username = localStorage.getItem('username');
        const detailActions = document.getElementById('detail-actions');
        if (detailActions) {
            if (username) {
                detailActions.style.display = 'flex';
            } else {
                detailActions.style.display = 'none';
            }
        }

        // Configurar Ações
        if (btnEdit) {
            btnEdit.addEventListener('click', () => {
                window.location.href = `../new_car/?id=${car.id}`;
            });
        }

        if (btnDelete) {
            btnDelete.addEventListener('click', async () => {
                const confirmDelete = confirm(`Deseja realmente excluir o carro ${car.modelo}?`);
                if (confirmDelete) {
                    try {
                        const result = await apiFetch<any>(`/api/v1/car/${car.id}/`, {
                            method: 'DELETE'
                        });
                        if (result) {
                            alert('Carro excluído com sucesso!');
                            window.location.href = '../cars/';
                        } else {
                            alert('Falha ao excluir carro.');
                        }
                    } catch (err: any) {
                        alert('Erro ao excluir carro: ' + err.message);
                    }
                }
            });
        }
    }
});
