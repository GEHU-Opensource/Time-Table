from datetime import timedelta
from pathlib import Path

import environ
from csp.constants import NONCE, NONE, SELF

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

ENV = env.str("ENV")
if ENV not in {"dev", "test", "prod"}:
    raise environ.ImproperlyConfigured("ENV must be dev, test or prod")

SECRET_KEY = env.str("SECRET_KEY")
SECRET_KEY_FALLBACKS = env.list("SECRET_KEY_FALLBACKS", default=[])
DEBUG = ENV == "dev" and env.bool("DEBUG", default=False)
SECURE = env.bool("SECURE", default=ENV == "prod")

BASE_DOMAIN = env.str("BASE_DOMAIN").lower()
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[f".{BASE_DOMAIN}"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[f"https://*.{BASE_DOMAIN}"])
HEALTH_PATH = "/healthz/"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "axes",
    "csp",
    "procrastinate.contrib.django",
    "core",
    "timetable",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.tenancy.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

_pug_loader = (
    "pypugjs.ext.django.Loader",
    (
        "django.template.loaders.filesystem.Loader",
        "django.template.loaders.app_directories.Loader",
    ),
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "loaders": [_pug_loader],
            "builtins": ["pypugjs.ext.django.templatetags"],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "csp.context_processors.nonce",
                "core.context.perms",
            ],
        },
    }
]

DATABASES = {
    "default": {
        **env.db_url("DATABASE_URL"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "sslmode": env.str("DB_SSLMODE", default="verify-full" if ENV == "prod" else "prefer"),
        },
        "TEST": {"NAME": env.str("TEST_DB_NAME", default=None)},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "core.auth.TenantBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin"
LOGOUT_REDIRECT_URL = "login"
PASSWORD_RESET_TIMEOUT = 3600
INVITE_TTL = timedelta(hours=72)

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "__Host-session" if SECURE else "session"
SESSION_COOKIE_SECURE = SECURE
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 8 * 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_USE_SESSIONS = True
MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

SECURE_SSL_REDIRECT = SECURE
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if SECURE else None
SECURE_HSTS_SECONDS = 31536000 if SECURE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE
SECURE_HSTS_PRELOAD = SECURE
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF, NONCE],
        "style-src": [SELF],
        "img-src": [SELF, "data:"],
        "connect-src": [SELF],
        "object-src": [NONE],
        "base-uri": [NONE],
        "frame-ancestors": [NONE],
        "form-action": [SELF],
    }
}

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_IPWARE_PROXY_COUNT = 1 if SECURE else 0
AXES_IPWARE_META_PRECEDENCE_ORDER = (
    ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"] if SECURE else ["REMOTE_ADDR"]
)
AXES_ENABLED = ENV != "test"

OTP_TOTP_ISSUER = "Time-Table"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if SECURE
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
FILE_UPLOAD_HANDLERS = ["django.core.files.uploadhandler.MemoryFileUploadHandler"]

vars().update(env.email_url("EMAIL_URL", default="consolemail://"))
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default=f"timetable@{BASE_DOMAIN}")

SOLVER_DEFAULT_SECONDS = 120
SOLVER_MAX_SECONDS = 600
SOLVER_WORKERS = 4
SOLVER_MEMORY_BYTES = 2 * 1024**3
SOLVER_MAX_MODEL_SIZE = 5_000_000
SOLVES_PER_TENANT_PER_HOUR = 10
STALE_SOLVE_GRACE = timedelta(minutes=5)

SILENCED_SYSTEM_CHECKS = ["auth.W004"]

LANGUAGE_CODE = "en"
TIME_ZONE = env.str("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = False
USE_TZ = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.request": {"level": "WARNING"},
        "django.security": {"level": "WARNING"},
    },
}
