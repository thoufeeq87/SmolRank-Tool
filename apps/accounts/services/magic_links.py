import hashlib
import math
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.tokens.api import add_tokens

from ..models import MagicLink, User

logger = logging.getLogger(__name__)


class MagicLinkEmailError(Exception):
    """The sign-in email could not be sent. Message is safe to show users."""


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email):
    return User.objects.normalize_email(email or "").strip().lower()


class MagicLinkRateLimited(MagicLinkEmailError):
    """Too many links requested for this address; message says how long to wait."""


def _minutes_until_allowed(user):
    """0 if another link may be sent now, else minutes until the oldest counted link ages out."""
    now = timezone.now()
    recent = list(
        user.magic_links.filter(created_at__gte=now - timedelta(hours=1))
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )
    limit = settings.MAGIC_LINK_MAX_PER_HOUR
    if len(recent) < limit:
        return 0
    frees_at = recent[len(recent) - limit] + timedelta(hours=1)
    return max(1, math.ceil((frees_at - now).total_seconds() / 60))


def build_link(token, next_url=""):
    url = settings.SITE_URL + reverse("accounts:verify", args=[token])
    return f"{url}?{urlencode({'next': next_url})}" if next_url else url


def request_link(email, next_url=""):
    """Create the user if new, then email a one-time link.

    Returns True if an email was sent. Inactive accounts return False silently.
    Raises MagicLinkRateLimited (with a wait time) when over the hourly limit.
    """
    user, _created = User.objects.get_or_create(email=normalize_email(email))
    if not user.is_active:
        return False
    wait = _minutes_until_allowed(user)
    if wait:
        raise MagicLinkRateLimited(
            f"Too many sign-in links requested. Please try again in {wait} minute{'s' if wait != 1 else ''}."
        )

    token = secrets.token_urlsafe(32)
    MagicLink.objects.create(
        user=user,
        token_hash=_hash(token),
        expires_at=timezone.now() + timedelta(minutes=settings.MAGIC_LINK_EXPIRY_MINUTES),
    )
    ctx = {
        "link": build_link(token, next_url),
        "minutes": settings.MAGIC_LINK_EXPIRY_MINUTES,
    }
    message = EmailMultiAlternatives(
        subject="Your SmolRank sign-in link",
        body=render_to_string("accounts/email/magic_link.txt", ctx),
        to=[user.email],
    )
    message.attach_alternative(render_to_string("accounts/email/magic_link.html", ctx), "text/html")
    try:
        message.send()
    except Exception as exc:
        logger.exception("Magic link email failed")
        raise MagicLinkEmailError("We couldn't send the email. Please try again in a moment.") from exc
    return True


def is_token_valid(token):
    """Check a token without consuming it (used by the GET confirmation page)."""
    return MagicLink.objects.filter(
        token_hash=_hash(token), used_at__isnull=True, expires_at__gt=timezone.now()
    ).exists()


def consume_token(token):
    """Atomically spend a token. Returns the user, or None if invalid/used/expired."""
    token_hash = _hash(token)
    now = timezone.now()
    with transaction.atomic():
        spent = MagicLink.objects.filter(
            token_hash=token_hash, used_at__isnull=True, expires_at__gt=now
        ).update(used_at=now)
        if spent != 1:
            return None
        user = MagicLink.objects.select_related("user").get(token_hash=token_hash).user
    if not user.is_active:
        return None
    grant_signup_bonus(user)
    return user


def grant_signup_bonus(user):
    """Give the welcome tokens once per user. The idempotency key makes repeats and races harmless."""
    amount = settings.SIGNUP_BONUS_TOKENS
    if amount <= 0:
        return
    try:
        add_tokens(
            user, amount, reason="Welcome bonus", reference="signup-bonus",
            idempotency_key=f"signup-bonus-{user.pk}",
        )
    except Exception:
        # Never block sign-in over this; the next sign-in retries safely.
        logger.exception("Could not grant the welcome bonus to user %s", user.pk)
