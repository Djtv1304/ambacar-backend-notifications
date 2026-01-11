"""
Base settings for Ambacar Notification Service.
"""
import os
import socket
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.core",
    "apps.notifications",
    "apps.analytics",
    "apps.synchronization",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database - PostgreSQL via dj-database-url (Supabase compatible)
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3"),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# REST Framework Configuration
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}

# =============================================================================
# drf-spectacular (OpenAPI/Swagger)
# =============================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Ambacar Notification Service API",
    "DESCRIPTION": "Microservicio de orquestación de notificaciones multi-canal para talleres Ambacar",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Events", "description": "Event dispatch and orchestration"},
        {"name": "Templates", "description": "Notification templates management"},
        {"name": "Orchestration", "description": "Service phase orchestration configuration"},
        {"name": "Customers", "description": "Customer preferences and contact info"},
        {"name": "Push", "description": "Push notification subscriptions"},
        {"name": "Analytics", "description": "Notification analytics and metrics"},
        {"name": "Internal API", "description": "Service-to-service communication endpoints (require API key authentication)"},
    ],
}

# =============================================================================
# CORS Configuration
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if not DEBUG else []

# =============================================================================
# Celery Configuration
# =============================================================================
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_TRACK_STARTED = False  # Reduces PUBLISH commands (no "task started" events)
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Cancel long-running tasks on connection loss to prevent duplicate executions
# This will be the default behavior in Celery 6.0
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

# Optimization: Reduce Redis command usage (critical for Upstash free tier)
# Disable task events (we use django-db for results already)
CELERY_TASK_SEND_SENT_EVENT = False
CELERY_WORKER_SEND_TASK_EVENTS = False

# Heartbeat interval: adaptive based on Redis type
# Upstash has 310s idle timeout, so we use 240s to stay safely below that
# Local Redis can use default or shorter interval for faster failure detection
_redis_url = os.environ.get("REDIS_URL", "")
if _redis_url.startswith("rediss://"):
    CELERY_BROKER_HEARTBEAT = 240  # 4 minutes for Upstash SSL
else:
    CELERY_BROKER_HEARTBEAT = 60  # 1 minute for local Redis (faster failure detection)

# Disable prefetch to reduce memory and Redis commands on idle workers
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Optimization: Reduce BRPOP polling frequency (critical for Upstash free tier)
# Adaptive configuration based on Redis type (local vs SSL/Upstash)
_redis_url = os.environ.get("REDIS_URL", "")
_using_redis_ssl = _redis_url.startswith("rediss://")

if _using_redis_ssl:
    # Upstash Redis with SSL: Use optimized settings for remote SSL connections
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,  # 1 hour (Celery default)
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            socket.TCP_KEEPIDLE: 30,   # Seconds before sending keepalive probes
            socket.TCP_KEEPINTVL: 10,  # Interval between keepalive probes
            socket.TCP_KEEPCNT: 3,     # Number of failed probes before giving up
        },
        'max_connections': 5,
    }
else:
    # Local Redis without SSL: Use simpler, more stable settings
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 3600,  # 1 hour (Celery default)
        'socket_timeout': 120,  # Longer timeout for stable local connections
        'socket_connect_timeout': 10,  # Quick connect for local Redis
        'max_connections': 10,  # More connections for local Redis (no tier limits)
    }

# Limit broker connection pool (prevents connection leaks)
CELERY_BROKER_POOL_LIMIT = 5

# Expire task results after 24 hours (reduces database cleanup overhead)
CELERY_RESULT_EXPIRES = 86400  # 24 hours in seconds

# SSL Configuration for Redis (required for Upstash and other TLS Redis providers)
# Only apply SSL settings when using rediss:// scheme
_redis_url = os.environ.get("REDIS_URL", "")
if _redis_url.startswith("rediss://"):
    import ssl
    CELERY_BROKER_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }
    CELERY_REDIS_BACKEND_USE_SSL = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
    }

# =============================================================================
# Email Configuration (SMTP)
# =============================================================================
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@ambacar.com")

# =============================================================================
# WhatsApp Configuration (Evolution API)
# =============================================================================
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE", "")
EVOLUTION_TIMEOUT = int(os.environ.get("EVOLUTION_TIMEOUT", "30"))

# =============================================================================
# Push Notifications Configuration (VAPID)
# =============================================================================
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CONTACT_EMAIL = os.environ.get("VAPID_CONTACT_EMAIL", "admin@ambacar.com")

# =============================================================================
# Frontend URL (for email links)
# =============================================================================
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# =============================================================================
# Notification Service Settings
# =============================================================================
NOTIFICATION_SETTINGS = {
    "FALLBACK_DELAY_SECONDS": 600,  # 10 minutes before trying next channel
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF_BASE": 60,  # Base seconds for exponential backoff
}

# =============================================================================
# Internal API Security (Service-to-Service Communication)
# =============================================================================
INTERNAL_API_SECRET_KEY = os.environ.get(
    "INTERNAL_API_SECRET_KEY",
    "CHANGE_THIS_IN_PRODUCTION"  # Only for development
)
