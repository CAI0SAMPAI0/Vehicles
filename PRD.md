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

