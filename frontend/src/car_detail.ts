import { apiFetch } from './api';
import { API_BASE_URL } from './config';
import { showToast } from './toast';

interface CarDetails {
    id: number;
    brand: number | null;
    marca: string | null;
    modelo: string;
    ano_fabricacao: number | null;
    ano_modelo: number | null;
    placa: string | null;
    preco: number | null;
    moeda: string | null;
    foto: string | null;
    descricao: string | null;
}

let usdToBrlRate = 5.50;

async function fetchExchangeRate() {
    try {
        const res = await fetch('https://economia.awesomeapi.com.br/json/last/USD-BRL');
        if (res.ok) {
            const data = await res.json();
            if (data && data.USDBRL && data.USDBRL.bid) {
                usdToBrlRate = parseFloat(data.USDBRL.bid);
                console.log('Taxa de câmbio USD-BRL obtida:', usdToBrlRate);
            }
        }
    } catch (err) {
        console.error('Falha ao obter cotação:', err);
    }
}

function formatCurrency(val: number, currencyCode: string): string {
    if (currencyCode === 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0
        }).format(val);
    } else {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL',
            maximumFractionDigits: 0
        }).format(val);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Obter ID do carro da URL e buscar cotação
    await fetchExchangeRate();
    const urlParams = new URLSearchParams(window.location.search);
    const carId = urlParams.get('id');

    if (!carId) {
        showToast('Carro não especificado.', 'error');
        setTimeout(() => {
            window.location.href = '../cars/';
        }, 1500);
        return;
    }

    // 2. Elementos do DOM
    const backLink = document.getElementById('back-link');
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

    if (backLink) {
        backLink.addEventListener('click', (e) => {
            e.preventDefault();
            window.history.back();
        });
    }

    // 3. Buscar detalhes do carro
    try {
        const car = await apiFetch<CarDetails>(`/api/v1/car/${carId}/`);
        if (car) {
            renderCarDetails(car);
        } else {
            showToast('Não foi possível encontrar os detalhes do carro.', 'error');
            setTimeout(() => {
                window.location.href = '../cars/';
            }, 1500);
        }
    } catch (err) {
        console.error('Erro ao buscar detalhes do carro:', err);
        showToast('Erro ao carregar detalhes do carro.', 'error');
        setTimeout(() => {
            window.location.href = '../cars/';
        }, 1500);
    }

    function renderCarDetails(car: CarDetails) {
        const fotoUrl = car.foto 
            ? (car.foto.startsWith('http') ? car.foto : `${API_BASE_URL}${car.foto}`) 
            : '';
        
        const currentCurrency = car.moeda || 'BRL';
        let precoFormatado = '';
        let precoConvertido = '';

        if (car.preco) {
            if (currentCurrency === 'USD') {
                precoFormatado = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(car.preco);
                const valorEmBrl = car.preco * usdToBrlRate;
                precoConvertido = ` (~ ` + new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(valorEmBrl) + `)`;
            } else {
                precoFormatado = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(car.preco);
                const valorEmUsd = car.preco / usdToBrlRate;
                precoConvertido = ` (~ ` + new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(valorEmUsd) + `)`;
            }
        } else {
            precoFormatado = 'Preço sob consulta';
        }

        if (photoContainer) {
            if (fotoUrl) {
                photoContainer.innerHTML = `<img src="${fotoUrl}" alt="${car.marca || ''} ${car.modelo}" loading="eager" fetchpriority="high" decoding="async" class="img-fade-in" onload="this.classList.add('loaded')">`;
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
        if (valueDisplay) {
            valueDisplay.innerHTML = `${precoFormatado}<span style="font-size: 0.95rem; color: var(--text-dim); font-weight: 400; margin-left: 0.5rem;">${precoConvertido}</span>`;
        }

        // Configurar Simulador de Financiamento se houver preço
        const simCard = document.getElementById('financing-simulator-card');
        const simEntrada = document.getElementById('sim-entrada') as HTMLInputElement | null;
        const simParcelas = document.getElementById('sim-parcelas') as HTMLSelectElement | null;
        const simResultValue = document.getElementById('sim-result-value');

        if (car.preco && simCard && simEntrada && simParcelas && simResultValue) {
            simCard.style.display = 'block';
            
            // Entrada padrão de 30% arredondada
            const defaultEntrada = Math.round(car.preco * 0.3);
            simEntrada.value = formatCurrency(defaultEntrada, currentCurrency);

            const calculateFinancing = () => {
                if (!car.preco) return;
                
                let entradaVal = 0;
                const cleanStr = simEntrada.value.replace(/\D/g, '');
                if (cleanStr) {
                    entradaVal = parseFloat(cleanStr);
                }
                
                const financedAmount = car.preco - entradaVal;
                if (financedAmount <= 0) {
                    simResultValue.textContent = 'R$ 0,00';
                    return;
                }
                
                const months = parseInt(simParcelas.value) || 48;
                const monthlyInterestRate = 0.015; // Taxa de 1.5% a.m.
                
                // Fórmula Price: P = (A * i) / (1 - (1 + i)^-n)
                const installment = (financedAmount * monthlyInterestRate) / (1 - Math.pow(1 + monthlyInterestRate, -months));
                
                simResultValue.textContent = formatCurrency(installment, currentCurrency);
            };

            simEntrada.addEventListener('input', () => {
                let val = simEntrada.value.replace(/\D/g, '');
                if (val) {
                    const numberVal = parseFloat(val);
                    simEntrada.value = formatCurrency(numberVal, currentCurrency);
                } else {
                    simEntrada.value = '';
                }
                calculateFinancing();
            });

            simParcelas.addEventListener('change', calculateFinancing);
            
            // Cálculo inicial
            calculateFinancing();
        }
        
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

        // Configurar Botão de WhatsApp
        const btnWhatsapp = document.getElementById('btn-whatsapp') as HTMLAnchorElement | null;
        const whatsappBtnContainer = document.getElementById('whatsapp-btn-container');
        if (btnWhatsapp && whatsappBtnContainer) {
            const contactPhone = "5511999999999"; // Telefone fictício da concessionária
            const messageText = `Olá! Gostaria de mais informações sobre o ${car.marca || ''} ${car.modelo} (${car.ano_modelo || car.ano_fabricacao || ''}) anunciado por ${precoFormatado} no AutoDrive. Link: ${window.location.href}`;
            btnWhatsapp.href = `https://wa.me/${contactPhone}?text=${encodeURIComponent(messageText)}`;
            whatsappBtnContainer.style.display = 'block';
        }

        // Configurar Ações
        if (btnEdit) {
            btnEdit.addEventListener('click', () => {
                window.location.href = `../new_car/?id=${car.id}`;
            });
        }

        // Configurar Ações do Modal Customizado
        const confirmModal   = document.getElementById('confirm-modal');
        const modalCarName   = document.getElementById('modal-car-name');
        const modalCancel    = document.getElementById('modal-cancel-btn');
        const modalConfirm   = document.getElementById('modal-confirm-btn');

        if (btnDelete && confirmModal && modalCarName && modalCancel && modalConfirm) {
            btnDelete.addEventListener('click', () => {
                modalCarName.textContent = `${car.marca || ''} ${car.modelo}`;
                confirmModal.style.display = 'flex';
            });

            const closeModal = () => {
                confirmModal.style.display = 'none';
            };

            modalCancel.addEventListener('click', closeModal);
            
            // Fecha ao clicar fora (backdrop)
            confirmModal.addEventListener('click', (e) => {
                if (e.target === confirmModal) closeModal();
            });

            modalConfirm.addEventListener('click', async () => {
                closeModal();
                try {
                    const result = await apiFetch<any>(`/api/v1/car/${car.id}/`, {
                        method: 'DELETE'
                    });
                    if (result) {
                        showToast('Carro excluído com sucesso!', 'success');
                        setTimeout(() => {
                            window.location.href = '../cars/';
                        }, 1500);
                    } else {
                        showToast('Falha ao excluir carro.', 'error');
                    }
                } catch (err: any) {
                    showToast('Erro ao excluir carro: ' + err.message, 'error');
                }
            });
        }
    }
});
