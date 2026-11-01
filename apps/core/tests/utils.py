from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client

from apps.tokens import add_tokens, get_balance

# Admin base path as configured by ADMIN_URL, e.g. "/secret-path/". Use instead of hardcoding "/admin/".
ADMIN = "/" + settings.ADMIN_URL


def auth_client(**client_kwargs):
    """A test client already signed in as a regular (non-staff) user."""
    client = Client(**client_kwargs)
    user, _ = get_user_model().objects.get_or_create(email="tester@example.com")
    if get_balance(user) < 1000:
        add_tokens(user, 1000, reason="test funds")
    client.force_login(user)
    return client
