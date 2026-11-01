import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .database import build_databases


def _flag(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


DEBUG = False

# PostgreSQL only: raises ImproperlyConfigured if DATABASE_URL is missing.
DATABASES = build_databases(require_url=True)
EMAIL_BACKEND = "apps.accounts.email_backends.resend.ResendEmailBackend"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Never run production on the public fallback key: sessions and CSRF tokens would be forgeable.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY to a unique random value of at least 50 characters. Generate one with: "
        'python -c "import secrets; print(secrets.token_urlsafe(64))"'
    )

# Static files: WhiteNoise serves what collectstatic gathered, compressed and with hashed file
# names (so browsers cache them safely and re-download only when they change).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HTTPS-only cookies and redirects. Behind a TLS-terminating proxy (Railway, Render, nginx...)
# also set DJANGO_BEHIND_PROXY=True, otherwise the HTTPS redirect loops. Only enable that when
# the proxy really overwrites X-Forwarded-Proto, because clients could otherwise spoof it.
SESSION_COOKIE_SECURE = _flag("DJANGO_SECURE_COOKIES", True)
CSRF_COOKIE_SECURE = _flag("DJANGO_SECURE_COOKIES", True)
SECURE_SSL_REDIRECT = _flag("DJANGO_SSL_REDIRECT", True)
if _flag("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS starts short so a mistake is recoverable; raise it (e.g. 31536000) once HTTPS is confirmed.
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", 3600))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _flag("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _flag("DJANGO_HSTS_PRELOAD", False)
