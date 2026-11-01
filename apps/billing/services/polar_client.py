from django.conf import settings
from polar.v2026_10 import Polar

from ..exceptions import BillingConfigError

VALID_SERVERS = ("sandbox", "production")


def get_client():
    """Polar SDK client for the server chosen by POLAR_SERVER (sandbox by default)."""
    if settings.POLAR_SERVER not in VALID_SERVERS:
        raise BillingConfigError(
            f"POLAR_SERVER must be one of {VALID_SERVERS}, got {settings.POLAR_SERVER!r}."
        )
    if not settings.POLAR_ACCESS_TOKEN:
        raise BillingConfigError("POLAR_ACCESS_TOKEN is not configured.")
    return Polar(settings.POLAR_ACCESS_TOKEN, environment=settings.POLAR_SERVER)
