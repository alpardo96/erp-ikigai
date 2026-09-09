"""
Django settings for config project.
ARCHIVO DE CONFIGURACIÓN CONTABLE Y OPERATIVO - ERP IKIGAI
"""

from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================================================================
# CARGA NATIVA DE VARIABLES DE ENTORNO DESDE .ENV
# =========================================================================
# Leemos el archivo .env ubicado en la raíz del proyecto para evitar
# exponer credenciales y secretos contables de base de datos en GitHub.
# Esto mantiene la higiene y seguridad de la configuración.
env_path = BASE_DIR / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Ignoramos líneas vacías y comentarios
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

# =========================================================================
# PARÁMETROS BÁSICOS Y SECRETOS
# =========================================================================
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG')
ALLOWED_HOSTS = ['*']

csrf_trusted = os.getenv('CSRF_TRUSTED_ORIGINS')
if csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted.split(',') if origin.strip()]

# Aplicaciones instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Módulos del ERP
    'core',
    'usuarios',
    'empresas',
    'contable',
    'productos',
    'facturacion',
    'tesoreria',
    'impuestos',
    'migracion',
]

# AUTO-DESCUBRIMIENTO DE VERTICALIDADES
# =========================================================================
verticalidades_path = BASE_DIR / 'verticalidades'
if verticalidades_path.exists() and verticalidades_path.is_dir():
    for item in verticalidades_path.iterdir():
        if item.is_dir() and (item / '__init__.py').exists():
            # Añadir a INSTALLED_APPS si es un paquete válido
            if item.name == 'agricola':
                # Módulo agrícola actúa como contenedor de sub-módulos
                for subitem in item.iterdir():
                    if subitem.is_dir() and (subitem / '__init__.py').exists():
                        sub_app_name = f'verticalidades.agricola.{subitem.name}'
                        if sub_app_name not in INSTALLED_APPS:
                            INSTALLED_APPS.append(sub_app_name)
            else:
                app_name = f'verticalidades.{item.name}'
                if app_name not in INSTALLED_APPS:
                    INSTALLED_APPS.append(app_name)


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.context_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =========================================================================
# CONFIGURACIÓN DE BASE DE DATOS (PostgreSQL)
# =========================================================================
# Usamos PostgreSQL para todos los entornos de desarrollo, producción y pruebas,
# cargando las credenciales de forma segura desde el archivo de configuración .env.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

AUTHENTICATION_BACKENDS = [
    'usuarios.backends.CaseInsensitiveModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =========================================================================
# CONFIGURACIÓN DE IA (Google Gemini)
# =========================================================================
# API Key para el motor de extracción inteligente de facturas.
# Obtener en: https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
