# Product Requirements Document (PRD) - AutoDrive (Carros)

## 1. Visão Geral do Produto
O **AutoDrive** (também denominado **Carros**) é um sistema de gerenciamento de inventário de veículos (garagem virtual). A plataforma permite a visualização, busca, cadastro, edição e exclusão de carros, contando com enriquecimento automático de descrições através de Inteligência Artificial e armazenamento em nuvem de fotos de veículos.

---

## 2. Personas e Casos de Uso

### 2.1 Visitante (Público)
- **Visualização da Garagem**: Visualizar a lista completa de veículos ativos e disponíveis.
- **Filtro e Busca**: Buscar veículos por nome do modelo, marca ou palavra-chave contida na descrição (bio), além de filtrar especificamente por marca.
- **Detalhes do Veículo**: Acessar a página de detalhes de um veículo para visualizar todas as especificações e a descrição gerada.

### 2.2 Administrador / Usuário Autenticado
- **Autenticação**: Cadastrar-se na plataforma, efetuar login e logout com segurança.
- **Gerenciamento de Inventário**:
  - Cadastrar novos veículos informando marca, modelo, ano de fabricação, ano do modelo, placa, valor, foto e descrição.
  - Atualizar os dados de qualquer veículo cadastrado.
  - Excluir veículos do inventário.
- **Geração de Bio por IA**: Gerar automaticamente descrições comerciais otimizadas e curtas ao cadastrar ou atualizar veículos.

---

## 3. Requisitos Funcionais Implementados

### 3.1 Autenticação e Autorização
- Sistema duplo de suporte:
  1. **Autenticação Baseada em Sessão**: Integrada com views do Django e Django Templates para o painel administrativo clássico.
  2. **Autenticação por Token**: Usando tokens do Django armazenados em `localStorage` (`auth_token`) no cliente para proteger e autorizar requisições do frontend SPA/Vite.

### 3.2 Cadastro e Gerenciamento de Veículos
- **Campos do Veículo**:
  - `model` (Modelo): Texto curto.
  - `brand` (Marca): Chave estrangeira para o modelo Brand (relação protegida).
  - `factory_year` (Ano de Fabricação): Inteiro (opcional).
  - `model_year` (Ano do Modelo): Inteiro (opcional).
  - `plate` (Placa): Texto (opcional, máximo 10 caracteres).
  - `value` (Valor): Float/Decimal (opcional).
  - `photo` (Foto): Imagem salva no Cloudinary (opcional).
  - `bio` (Descrição): Texto descritivo (opcional).
- **Inventário Consolidado**: Monitoramento em tempo real do total de veículos e valor total acumulado no estoque (atualizado dinamicamente via signals).

### 3.3 Integração com Inteligência Artificial (Groq / Llama 3.1)
- **Geração de Bio**: Endpoint/Script que envia marca, modelo e ano para a API da Groq (modelo `llama-3.1-8b-instant`) e retorna uma descrição de vendas concisa com até 250 caracteres.
- **Seed de Dados com IA (Carga Inicial)**: Script em `backend/openai_api/cars_ai.py` que:
  - Lê marcas do arquivo `brands.csv`.
  - Solicita modelos populares à IA em formato JSON estruturado.
  - Salva-os no banco de dados.
  - Busca imagens no Wikimedia Commons e faz upload automático para o Cloudinary.

### 3.4 Desempenho e Caching
- Caching de consultas pesadas da API de veículos (como paginação, busca e filtros) no Redis (ou LocMemCache em desenvolvimento) para respostas ultrarrápidas, com invalidação automática de cache disparada por Signals do Django quando um veículo é modificado ou deletado.

---

## 4. Requisitos Não-Funcionais

- **Banco de Dados**: PostgreSQL (configuração flexível via `dj_database_url` para ambientes de nuvem como Railway).
- **Armazenamento de Mídia**: Integração nativa com Cloudinary via `django-cloudinary-storage` para persistência confiável das imagens de veículos.
- **Interface e Design**: Interface responsiva com tema escuro (dark mode), tipografia moderna (Google Fonts - Barlow e Bebas Neue) e transições suaves, usando Vanilla CSS.

---

## 5. Sprints e Acompanhamento de Tarefas

Nesta seção, listamos as sprints de desenvolvimento para a melhoria contínua da IA e integridade do backend.

- [X] **Sprint 1: Análise e Planejamento**
  - [X] Mapear o funcionamento do Django no Hugging Face Spaces.
  - [X] Investigar a estrutura de carregamento do app `cars` e controle de processos de segundo plano.
- [X] **Sprint 2: Desenvolvimento do Worker de Segundo Plano (`worker.py`)**
  - [X] Criar o arquivo [worker.py](file:///C:/Users/caio/Documents/GitHub/Vehicles/backend/cars/worker.py) com loop infinito de atualização automática.
  - [X] Implementar busca e download automático de imagens (com integração com Cloudinary) e classificação automática de categoria usando a API da Groq.
- [X] **Sprint 3: Lock Robusto para Multi-Workers e Inicialização (`apps.py`)**
  - [X] Refatorar a classe `CarsConfig` em [apps.py](file:///C:/Users/caio/Documents/GitHub/Vehicles/backend/cars/apps.py) para utilizar verificação de PID ao gerenciar locks de worker.
  - [X] Integrar a inicialização do worker de segundo plano ao invés de rodar uma única varredura.
- [X] **Sprint 4: Mecanismo de Ping/Keep-Alive**
  - [X] Implementar função `ping_self()` no worker para fazer chamadas HTTP à URL pública do Hugging Face Space para evitar inatividade.
- [X] **Sprint 5: Validação Final e Commit**
  - [X] Executar testes locais básicos para garantir que a sintaxe Python e as importações do Django estão corretas.
  - [X] Realizar o commit das modificações e fazer o `git push`.
- [X] **Sprint 6: Concorrência e Paralelismo de Workers de IA**
  - [X] Separar a rotina do [worker.py](file:///C:/Users/caio/Documents/GitHub/Vehicles/backend/cars/worker.py) em duas threads daemon paralelas (`TextAIWorkerThread` e `PhotoScraperWorkerThread`).
  - [X] Garantir que a thread de IA de texto classifique as categorias e gere as bios sem aguardar pela busca/download de imagens de outros carros.
  - [X] Implementar o atributo `skip_signal` em [signals.py](file:///C:/Users/caio/Documents/GitHub/Vehicles/backend/cars/signals.py) e [utils.py](file:///C:/Users/caio/Documents/GitHub/Vehicles/backend/cars/utils.py) para contornar disparos recursivos do post_save de forma segura.
- [X] **Sprint 7: Otimizações de Imagem no Frontend**
  - [X] Implementar carregamento prioritário (`loading="eager"` e `fetchpriority="high"`) nas imagens acima da dobra na listagem em [cars.ts](file:///C:/Users/caio/Documents/GitHub/Vehicles/frontend/src/cars.ts).
  - [X] Configurar lazy loading e baixo fetch priority nas imagens abaixo da dobra na listagem.
  - [X] Adicionar decodificação assíncrona (`decoding="async"`) e efeitos CSS de fade-in no [index.css](file:///C:/Users/caio/Documents/GitHub/Vehicles/frontend/src/index.css).
  - [X] Otimizar a imagem principal no detalhamento em [car_detail.ts](file:///C:/Users/caio/Documents/GitHub/Vehicles/frontend/src/car_detail.ts).
- [ ] **Sprint 8: Sugestões de Melhorias de Sistema (Backlog)**
  - [X] **Melhoria 1**: Conversão automática das fotos para WebP com compressão leve no Django (otimização de banda/armazenamento).
  - [ ] **Melhoria 2**: Implementar Placeholders Base64/Blurhash inline no JSON das APIs.
  - [ ] **Melhoria 3**: Configurar Service Workers e cache local de assets no navegador (PWA).
  - [X] **Melhoria 4**: Adicionar máscaras dinâmicas de input no cadastro (placa, valor, ano) com normalização de dados para o backend.
  - [X] **Melhoria 5**: Substituir popups e confirms nativos por modais em CSS (design premium customizado).
  - [ ] **Melhoria 6**: Integrar autenticação por JWT e Refresh Tokens.
  - [X] **Melhoria 7**: Adicionar fila de retentativas com backoff exponencial para erros de rate limit (`429`) da Groq na API.
  - [X] **Melhoria 8**: Adicionar ordenação (preco/ano) diretamente nos filtros e buscas (backend & frontend).
  - [ ] **Melhoria 9**: Monitorar links de imagens quebrados via cron semanal de checagem.
  - [ ] **Melhoria 10**: Configurar suporte multi-idiomas (i18n).
  - [X] **Melhoria Extra (Design)**: Correção da sobreposição do título 'GARAGEM' (z-index) e redimensionamento responsivo dos inputs no mobile.
- [ ] **Sprint 9: Novidades e Inovações (Backlog)**
  - [ ] **Novidade 1**: Criar painel comparador de até 3 veículos lado a lado.
  - [ ] **Novidade 2**: Busca semântica conversacional usando embeddings da Groq e `pgvector`.
  - [X] **Novidade 3**: Widget simulador de parcelas de financiamento na tela de detalhes (interativo com taxa est. de 1.5% a.m.).
  - [ ] **Novidade 4**: Histórico de depreciação FIPE com gráfico interativo.
  - [X] **Novidade 5**: Link de contato/interesse direto no WhatsApp contendo dados consolidados do veículo e link da página.
  - [ ] **Novidade 6**: Permitir cadastro de múltiplas fotos com carrossel interativo.
  - [ ] **Novidade 7**: Extração inteligente da ficha técnica completa estruturada por IA.
  - [ ] **Novidade 8**: Dashboard administrativo com estatísticas e relatórios de buscas.
  - [ ] **Novidade 9**: Alerta de redução de preço por e-mail para veículos favoritados.
  - [ ] **Novidade 10**: Chatbot integrado para recomendação e suporte de vendas de carros.
  - [X] **Novidade Extra (Multi-Moedas)**: Suporte a salvar carros em USD ou BRL com formatação automática de inputs e conversão dinâmica em tempo real via AwesomeAPI.

