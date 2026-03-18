from __future__ import annotations

import os
from pathlib import Path


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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
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
    "automation.run_scheduled_template": {"queue": "default"},
    "backtests.run_backtest_job": {"queue": "default"},
    "jobs.run_smoke_job": {"queue": "default"},
    "screens.run_screen_job": {"queue": "default"},
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
ARTIFACT_STORAGE_BACKEND = _env("ARTIFACT_STORAGE_BACKEND", "filesystem")
ARTIFACT_STORAGE_ROOT = Path(_env("ARTIFACT_STORAGE_ROOT", str(BASE_DIR / ".artifacts")))
ARTIFACT_ORPHAN_RETENTION_HOURS = float(_env("ARTIFACT_ORPHAN_RETENTION_HOURS", "24") or "24")

EMAIL_BACKEND = _env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = _env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(_env("EMAIL_PORT", "25") or "25")
EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "") or ""
EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "") or ""
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = _env("DEFAULT_FROM_EMAIL", "greenblatt@example.test") or "greenblatt@example.test"
