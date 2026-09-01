FROM python:3.12.10-slim

# Impedir o Python de gerar arquivos .pyc e forçar logs instantâneos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copiar os pacotes do backend e instalar
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código-fonte (incluindo backend e frontend)
COPY . .

# Mudar o diretório de trabalho para a pasta do backend
WORKDIR /app/backend

# Coletar arquivos estáticos em produção usando o WhiteNoise
RUN python manage.py collectstatic --noinput

# Expor porta padrão (compatível com Render, Hugging Face, Railway)
EXPOSE 8000
ENV PORT=8000

# Rodar migrações, criar superusuário admin e iniciar o servidor Gunicorn usando a variável $PORT
CMD ["sh", "-c", "python manage.py migrate && python create_superuser.py && gunicorn app.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120"]
