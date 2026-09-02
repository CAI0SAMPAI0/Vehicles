import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, '.env'))
load_dotenv(os.path.join(BASE_DIR.parent, '.env'))

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-placeholder-change-me')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

allowed_hosts_env = os.getenv('ALLOWED_HOSTS')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()] if allowed_hosts_env else ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cars',
    'accounts',
    'openai_api',
]

MIDDLEWARE = [
    'app.middleware.SimpleCORSMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['app/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

# Database configuration (PostgreSQL em produção, SQLite local/fallback)
import dj_database_url
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.strip():
    DATABASES = {
        'default': dj_database_url.parse(
            database_url.strip(),
            conn_max_age=600,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files — WhiteNoise serve em produção
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MANIFEST_STRICT = False
# Inclui a pasta images/ como arquivos estáticos — servidos pelo WhiteNoise em produção
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'images'),
]

# Media files (Cloudinary em produção, local em desenvolvimento)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

if not DEBUG and all(CLOUDINARY_STORAGE.values()):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR

CSRF_TRUSTED_ORIGINS = [
    'https://autodrivecars.netlify.app',
    'https://*.vercel.app',
    'https://*.onrender.com',
    'https://*.netlify.app',
    'https://*.hf.space',
    'http://localhost:3000',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'http://localhost:4173',
    'https://carros-j99v.onrender.com',
]

space_id = os.getenv('SPACE_ID')
if space_id and '/' in space_id:
    user, space = space_id.split('/')
    user_name = user.replace('.', '-').replace('_', '-').lower()
    space_name = space.replace('.', '-').replace('_', '-').lower()
    CSRF_TRUSTED_ORIGINS.append(f'https://{user_name}-{space_name}.hf.space')

csrf_env = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_env:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in csrf_env.split(',') if origin.strip()])

# Configurações de cookies para suporte a CORS e Sessões Cruzadas (Cross-Origin)
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True


redis_url = os.getenv("REDIS_URL")
if redis_url:
    if not (redis_url.startswith("redis://") or redis_url.startswith("rediss://")):
        redis_url = f"redis://{redis_url}"
    if "?" in redis_url:
        redis_url = f"{redis_url}&protocol=2"
    else:
        redis_url = f"{redis_url}?protocol=2"
        
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": redis_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "CONNECTION_POOL_KWARGS": {
                    "protocol": 2,
                },
            }
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }