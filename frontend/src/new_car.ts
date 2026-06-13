import { apiFetch } from './api';
import { API_BASE_URL } from './config';
import { showToast } from './toast';

interface Brand {
    id: number;
    name: string;
}

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
    // 1. Verificar autenticação
    const username = localStorage.getItem('username');
    if (!username) {
        showToast('Você precisa estar logado para acessar esta página.', 'error');
        setTimeout(() => {
            window.location.href = '../login/';
        }, 1500);
        return;
    }

    const brandSelect = document.getElementById('brand') as HTMLSelectElement | null;
    const carForm = document.getElementById('car-form') as HTMLFormElement | null;
    const pageTitle = document.getElementById('page-title') as HTMLHeadingElement | null;
    const pageSub = document.getElementById('page-subtitle') as HTMLParagraphElement | null;
    const submitBtn = document.getElementById('btn-save-car') as HTMLButtonElement | null;

    // Obter ID do carro se estivermos editando
    const urlParams = new URLSearchParams(window.location.search);
    const carId = urlParams.get('id');
    const isEditMode = !!carId;

    // 2. Carregar marcas dinamicamente
    try {
        const brands = await apiFetch<Brand[]>('/api/v1/brands/');
        if (brands && brandSelect) {
            brandSelect.innerHTML = '<option value="" class="bg-brand-panel">Selecione uma marca</option>';
            brands.forEach(brand => {
                const option = document.createElement('option');
                option.value = brand.id.toString();
                option.textContent = brand.name;
                option.className = 'bg-brand-panel';
                brandSelect.appendChild(option);
            });
        }
    } catch (err) {
        console.error('Erro ao carregar marcas:', err);
    }

    // 3. Se for modo edição, carregar os dados do carro e preencher o formulário
    if (isEditMode && carId) {
        if (pageTitle) pageTitle.textContent = 'Editar Veículo';
        if (pageSub) pageSub.textContent = 'Atualize as informações do automóvel';
        if (submitBtn) submitBtn.textContent = 'Salvar Alterações';

        try {
            const car = await apiFetch<CarDetails>(`/api/v1/car/${carId}/`);
            if (car && carForm) {
                const modelInput = document.getElementById('model') as HTMLInputElement | null;
                const factoryYearInput = document.getElementById('factory_year') as HTMLInputElement | null;
                const modelYearInput = document.getElementById('model_year') as HTMLInputElement | null;
                const plateInput = document.getElementById('plate') as HTMLInputElement | null;
                const valueInput = document.getElementById('value') as HTMLInputElement | null;
                const bioInput = document.getElementById('bio') as HTMLTextAreaElement | null;

                if (modelInput) modelInput.value = car.modelo;
                if (brandSelect && car.brand) brandSelect.value = car.brand.toString();
                if (factoryYearInput && car.ano_fabricacao) factoryYearInput.value = car.ano_fabricacao.toString();
                if (modelYearInput && car.ano_modelo) modelYearInput.value = car.ano_modelo.toString();
                if (plateInput && car.placa) plateInput.value = car.placa;
                if (valueInput && car.preco) valueInput.value = car.preco.toString();
                if (bioInput && car.descricao) bioInput.value = car.descricao;
            }
        } catch (err) {
            console.error('Erro ao carregar detalhes do carro para edição:', err);
            showToast('Não foi possível carregar os dados do carro.', 'error');
        }
    }

    // 4. Submissão do formulário (Criação ou Edição)
    if (carForm) {
        carForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Usando FormData para suportar envio de arquivo/imagem
            const formData = new FormData(carForm);

            // Adicionar cabeçalho de autorização manual já que estamos usando fetch nativo para FormData
            const token = localStorage.getItem('auth_token');
            const headers: Record<string, string> = {};
            if (token) {
                headers['Authorization'] = `Token ${token}`;
            }

            const url = isEditMode 
                ? `${API_BASE_URL}/api/v1/car/${carId}/`
                : `${API_BASE_URL}/api/v1/car/create/`;

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers,
                    body: formData
                });

                const result = await response.json().catch(() => ({}));
                if (response.ok && result.success) {
                    showToast(isEditMode ? 'Carro atualizado com sucesso!' : 'Carro cadastrado com sucesso!', 'success');
                    setTimeout(() => {
                        window.location.href = '../cars/';
                    }, 1500);
                } else {
                    const errorMsg = result.error || (result.errors ? JSON.stringify(result.errors) : 'Erro desconhecido');
                    showToast('Erro ao salvar carro: ' + errorMsg, 'error');
                }
            } catch (err: any) {
                showToast('Erro de conexão ao salvar carro: ' + err.message, 'error');
            }
        });
    }
});
