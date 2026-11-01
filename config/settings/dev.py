import os

from .base import *  # noqa: F401,F403

# Tunnel hosts (ngrok / cloudflared) for testing webhooks locally, comma-separated, e.g.
# DJANGO_ALLOWED_HOSTS=abc123.ngrok-free.app
_extra_hosts = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Set DJANGO_DEBUG=False in .env to see the custom 404/500 pages locally.
# While a tunnel host is configured, debug defaults to OFF: with DEBUG on, anyone who has the
# public tunnel address would see Django's debug pages (settings, code, SQL).
DEBUG = os.environ.get("DJANGO_DEBUG", "False" if _extra_hosts else "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = ["localhost", "127.0.0.1", *_extra_hosts]
# Tunnels terminate HTTPS and forward plain HTTP: trust their forwarded scheme and allow their origin for POST forms.
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in _extra_hosts]
if _extra_hosts:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Serve admin/app static files straight from the apps, even with DEBUG off.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
