"""Security settings. The admin lives at a secret path so bots scanning /admin/ find nothing."""
import os
import re

from django.core.exceptions import ImproperlyConfigured

# Top-level paths the site already uses; an admin URL starting with one would shadow a real page.
RESERVED_PATHS = {"accounts", "tokens", "billing", "analyze", "results", "api", "static", "__errors__"}
_SEGMENT = r"[A-Za-z0-9._~-]+"


def normalize_admin_url(value):
    """Return the admin path as 'some/path/' (no leading slash, one trailing slash)."""
    value = (value or "admin").strip().strip("/")
    if not re.fullmatch(rf"{_SEGMENT}(/{_SEGMENT})*", value):
        raise ImproperlyConfigured(
            "ADMIN_URL may only contain letters, numbers, '-', '_', '.', '~' and '/' between segments."
        )
    if any(set(segment) <= {"."} for segment in value.split("/")):
        raise ImproperlyConfigured("ADMIN_URL segments cannot be '.' or '..'.")
    if value.split("/")[0].lower() in RESERVED_PATHS:
        raise ImproperlyConfigured(f"ADMIN_URL {value!r} clashes with an existing site path.")
    return value + "/"


# Set ADMIN_URL in .env to a long random string, e.g. ADMIN_URL=k3v9-private-x7Qm2pLw
ADMIN_URL = normalize_admin_url(os.environ.get("ADMIN_URL"))
