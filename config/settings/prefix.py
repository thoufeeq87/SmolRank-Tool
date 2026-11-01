"""Serving the app under a sub-path, e.g. https://thoufai.com/smolrank/ (DJANGO_URL_PREFIX=/smolrank).

The reverse proxy in front of Django must STRIP the prefix before forwarding (/smolrank/analyze/ -> /analyze/).
Django then adds the prefix back to every link it generates (reverse(), {% url %}, redirects, static files).
Leave DJANGO_URL_PREFIX unset to serve from the root of the domain.
"""
import os

_raw = os.environ.get("DJANGO_URL_PREFIX", "").strip().strip("/")
URL_PREFIX = f"/{_raw}" if _raw else ""

if URL_PREFIX:
    FORCE_SCRIPT_NAME = URL_PREFIX
    # Keep our cookies off the other pages of the same domain (and theirs off ours).
    SESSION_COOKIE_PATH = URL_PREFIX
    CSRF_COOKIE_PATH = URL_PREFIX
