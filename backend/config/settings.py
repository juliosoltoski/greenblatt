from __future__ import annotations

import os
from pathlib import Path

from apps.core.logging import build_logging_config
from apps.core.sentry import initialize_sentry

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = _env("DJANGO_SECRET_KEY", "dev-only-secret-key")  # noqa: S105
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,proxy")
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "rest_framework",
    "apps.accounts",
    "apps.automation",
    "apps.backtests",
    "apps.collaboration",
    "apps.core",
    "apps.jobs",
    "apps.screens",
    "apps.strategy_templates",
    "apps.universes",
    "apps.workspaces",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if _env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env("POSTGRES_DB", "greenblatt"),
            "USER": _env("POSTGRES_USER", "greenblatt"),
            "PASSWORD": _env("POSTGRES_PASSWORD", "greenblatt"),
            "HOST": _env("POSTGRES_HOST", "postgres"),
            "PORT": _env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if _env("DJANGO_CACHE_BACKEND") == "redis":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _env("DJANGO_CACHE_LOCATION", _env("REDIS_URL", "redis://redis:6379/2")),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": _env("DJANGO_CACHE_LOCATION", "greenblatt-local-cache"),
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.core.throttling.BurstRateThrottle",
        "apps.core.throttling.SustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "burst": _env("DRF_THROTTLE_BURST", "240/min"),
        "anon": _env("DRF_THROTTLE_ANON", "120/min"),
        "login": _env("DRF_THROTTLE_LOGIN", "20/min"),
        "launch": _env("DRF_THROTTLE_LAUNCH", "60/hour"),
        "mutation": _env("DRF_THROTTLE_MUTATION", "240/hour"),
        "export": _env("DRF_THROTTLE_EXPORT", "120/hour"),
    },
}

REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = _env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = _env("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = _env_bool("CELERY_TASK_EAGER_PROPAGATES", False)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_SOFT_TIME_LIMIT = int(_env("CELERY_TASK_SOFT_TIME_LIMIT", "1500") or "1500")
CELERY_TASK_TIME_LIMIT = int(_env("CELERY_TASK_TIME_LIMIT", "1800") or "1800")
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "automation.send_notification_digests": {"queue": "default"},
    "automation.run_scheduled_template": {"queue": "default"},
    "backtests.run_backtest_job": {"queue": "default"},
    "core.run_provider_cache_warm_job": {"queue": "default"},
    "jobs.run_smoke_job": {"queue": "default"},
    "screens.run_screen_job": {"queue": "default"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = _env("DJANGO_SESSION_COOKIE_SAMESITE", "Lax") or "Lax"
CSRF_COOKIE_SAMESITE = _env("DJANGO_CSRF_COOKIE_SAMESITE", "Lax") or "Lax"
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_HTTPONLY = _env_bool("DJANGO_SESSION_COOKIE_HTTPONLY", True)
CSRF_COOKIE_HTTPONLY = _env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(_env("DJANGO_SECURE_HSTS_SECONDS", "0") or "0")
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", True)
X_FRAME_OPTIONS = _env("DJANGO_X_FRAME_OPTIONS", "DENY") or "DENY"
USE_X_FORWARDED_HOST = _env_bool("DJANGO_USE_X_FORWARDED_HOST", True)
SECURE_REFERRER_POLICY = _env("DJANGO_SECURE_REFERRER_POLICY", "same-origin") or "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = _env("DJANGO_SECURE_COOP", "same-origin") or "same-origin"
DATABASE_CONN_MAX_AGE = int(_env("DATABASE_CONN_MAX_AGE", "60") or "60")
if "default" in DATABASES:
    DATABASES["default"]["CONN_MAX_AGE"] = DATABASE_CONN_MAX_AGE
ARTIFACT_STORAGE_BACKEND = _env("ARTIFACT_STORAGE_BACKEND", "filesystem")
ARTIFACT_STORAGE_ROOT = Path(_env("ARTIFACT_STORAGE_ROOT", str(BASE_DIR / ".artifacts")))
ARTIFACT_ORPHAN_RETENTION_HOURS = float(_env("ARTIFACT_ORPHAN_RETENTION_HOURS", "24") or "24")
WORKSPACE_MAX_CONCURRENT_JOBS = int(_env("WORKSPACE_MAX_CONCURRENT_JOBS", "8") or "8")
WORKSPACE_MAX_CONCURRENT_RESEARCH_JOBS = int(_env("WORKSPACE_MAX_CONCURRENT_RESEARCH_JOBS", "2") or "2")
WORKSPACE_MAX_CONCURRENT_SMOKE_JOBS = int(_env("WORKSPACE_MAX_CONCURRENT_SMOKE_JOBS", "3") or "3")
MARKET_DATA_PROVIDER = (_env("MARKET_DATA_PROVIDER", "yahoo") or "yahoo").strip().lower().replace("-", "_")
MARKET_DATA_PROVIDER_FALLBACK = (_env("MARKET_DATA_PROVIDER_FALLBACK") or "").strip().lower().replace("-", "_") or None
ALPHA_VANTAGE_API_KEY = _env("ALPHA_VANTAGE_API_KEY")
ALPHA_VANTAGE_BASE_URL = _env("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query") or "https://www.alphavantage.co/query"
ALPHA_VANTAGE_MAX_CALLS_PER_MINUTE = int(_env("ALPHA_VANTAGE_MAX_CALLS_PER_MINUTE", "5") or "5")
SOCIAL_LOGIN_ENABLED = _env_bool("SOCIAL_LOGIN_ENABLED", False)
BILLING_ENABLED = _env_bool("BILLING_ENABLED", False)
SUPPORT_CONTACT_EMAIL = _env("SUPPORT_CONTACT_EMAIL", "support@example.test") or "support@example.test"

EMAIL_BACKEND = _env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = _env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(_env("EMAIL_PORT", "25") or "25")
EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "") or ""
EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "") or ""
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = _env("DEFAULT_FROM_EMAIL", "greenblatt@example.test") or "greenblatt@example.test"
SERVER_EMAIL = _env("SERVER_EMAIL", DEFAULT_FROM_EMAIL) or DEFAULT_FROM_EMAIL
ADMINS = [
    ("Ops", email)
    for email in _env_list("DJANGO_ADMINS")
]

LOG_LEVEL = _env("LOG_LEVEL", "INFO") or "INFO"
LOG_JSON = _env_bool("LOG_JSON", not DEBUG)
LOGGING = build_logging_config(log_level=LOG_LEVEL, json_logs=LOG_JSON)

SENTRY_DSN = _env("SENTRY_DSN")
SENTRY_ENVIRONMENT = _env("SENTRY_ENVIRONMENT", "development") or "development"
SENTRY_RELEASE = _env("SENTRY_RELEASE")
SENTRY_TRACES_SAMPLE_RATE = float(_env("SENTRY_TRACES_SAMPLE_RATE", "0") or "0")
SENTRY_PROFILES_SAMPLE_RATE = float(_env("SENTRY_PROFILES_SAMPLE_RATE", "0") or "0")
SENTRY_SEND_DEFAULT_PII = _env_bool("SENTRY_SEND_DEFAULT_PII", False)
METRICS_AUTH_TOKEN = _env("METRICS_AUTH_TOKEN")

initialize_sentry(
    dsn=SENTRY_DSN,
    environment=SENTRY_ENVIRONMENT,
    release=SENTRY_RELEASE,
    traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
    profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
    send_default_pii=SENTRY_SEND_DEFAULT_PII,
)
