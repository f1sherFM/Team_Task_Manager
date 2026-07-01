import os
from pathlib import Path

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
IS_RENDER = "RENDER" in os.environ


def load_local_env(env_path: Path) -> None:
    if load_dotenv is not None:
        load_dotenv(env_path)
        return

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_local_env(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


database_url = os.getenv("DATABASE_URL")
default_sqlite_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
ssl_required_default = bool(
    database_url and "render.com" in database_url and database_url.startswith("postgres")
)

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    os.getenv(
        "SECRET_KEY",
        "django-insecure-a!!w%ka5hor$9@ir^5e)25rbni&b&qjj(5(8tzsngwztl1(7)j",
    ),
)
DEBUG = env_bool("DEBUG", not IS_RENDER)
SENTRY_DSN = os.getenv("SENTRY_DSN")

allowed_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
render_external_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if render_external_hostname:
    allowed_hosts.append(render_external_hostname)
ALLOWED_HOSTS = list(dict.fromkeys(allowed_hosts))

csrf_trusted_origins = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if render_external_hostname:
    csrf_trusted_origins.append(f"https://{render_external_hostname}")
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(csrf_trusted_origins))
DEV_DASHBOARD_URL = os.getenv("DEV_DASHBOARD_URL", "http://127.0.0.1:8101")
KNOWLEDGE_SYSTEM_URL = os.getenv("KNOWLEDGE_SYSTEM_URL", "http://127.0.0.1:8102")
KNOWLEDGE_BASE_URL = os.getenv("KNOWLEDGE_BASE_URL", "http://127.0.0.1:8103")
TASK_MANAGER_URL = os.getenv("TASK_MANAGER_URL", "http://127.0.0.1:8104")
ECOSYSTEM_CURRENT_SERVICE = os.getenv("ECOSYSTEM_CURRENT_SERVICE", "team_task_manager")
ECOSYSTEM_URLS = {
    "dev_dashboard": DEV_DASHBOARD_URL,
    "knowledge_system": KNOWLEDGE_SYSTEM_URL,
    "knowledge_base": KNOWLEDGE_BASE_URL,
    "team_task_manager": TASK_MANAGER_URL,
}
ECOSYSTEM_APPS = [
    {"id": "dev_dashboard", "label": "Home", "url": DEV_DASHBOARD_URL},
    {"id": "knowledge_system", "label": "Knowledge", "url": KNOWLEDGE_SYSTEM_URL},
    {"id": "knowledge_base", "label": "Base", "url": KNOWLEDGE_BASE_URL},
    {"id": "team_task_manager", "label": "Tasks", "url": TASK_MANAGER_URL},
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
    "workspaces",
    "projects",
    "tasks",
    "comments",
    "activity",
    "api",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "team_task_manager.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.ecosystem",
            ],
        },
    },
]

WSGI_APPLICATION = "team_task_manager.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=default_sqlite_url,
        conn_max_age=600,
        ssl_require=env_bool("DB_SSL_REQUIRE", ssl_required_default),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")

USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [STATIC_DIR]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool("SECURE_PROXY_SSL_HEADER", IS_RENDER)
    else None
)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", IS_RENDER)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_RENDER)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", IS_RENDER)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if IS_RENDER else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_RENDER)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", IS_RENDER)

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=os.getenv(
            "SENTRY_ENVIRONMENT",
            "development" if DEBUG else "production",
        ),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
        send_default_pii=True,
    )

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Team Task Manager API",
    "DESCRIPTION": "API documentation for the Team Task Manager backend service.",
    "VERSION": "1.0.0",
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "core.logging_utils.ContextFormatter",
            "format": (
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "workspace=%(workspace)s project=%(project)s task=%(task)s "
                "user=%(user)s action=%(action)s"
            ),
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "ttm": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
