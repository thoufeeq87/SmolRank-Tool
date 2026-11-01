from django.contrib.auth.backends import ModelBackend

from .services.magic_links import consume_token


class MagicLinkBackend(ModelBackend):
    """Authenticate with a one-time token. Keeps ModelBackend's permission checks."""

    def authenticate(self, request, token=None, **kwargs):
        if not token:
            return None
        return consume_token(token)
