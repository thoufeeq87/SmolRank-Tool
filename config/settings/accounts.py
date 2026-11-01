"""Accounts / magic-link settings. Override via environment variable / .env."""
import os

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.MagicLinkBackend"]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "winnability:analyze"
LOGOUT_REDIRECT_URL = "winnability:landing"

# A magic link is valid for this long and works exactly once.
MAGIC_LINK_EXPIRY_MINUTES = int(os.environ.get("MAGIC_LINK_EXPIRY_MINUTES", 15))
# Max links emailed to one address per hour.
MAGIC_LINK_MAX_PER_HOUR = int(os.environ.get("MAGIC_LINK_MAX_PER_HOUR", 5))

# Base URL used to build absolute links inside emails.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")

# Email. Development prints emails in the terminal; production uses Resend.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "apps.accounts.email_backends.console.ConsoleEmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "SmolRank <onboarding@resend.dev>")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = int(os.environ.get("RESEND_TIMEOUT", 10))
