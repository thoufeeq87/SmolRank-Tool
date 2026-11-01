import logging

from django.conf import settings

from apps.tokens import add_tokens, consume_tokens, get_balance

from .analyzer import check_keyword
from .history import record_search

logger = logging.getLogger(__name__)


def token_cost():
    return settings.SMOLRANK_TOKEN_COST


def can_afford(user):
    return get_balance(user) >= token_cost()


def run_paid_check(user, keyword):
    """Charge the user, run the keyword check, refund if it fails.

    Raises apps.tokens.InsufficientTokens (nothing is run or recorded) when the
    balance is too low. Any failure after the charge refunds it, so users only
    pay for checks that return a result.
    """
    cost = token_cost()
    charge = consume_tokens(user, cost, reason="Keyword check", reference=f"check:{keyword}"[:255])
    try:
        result = check_keyword(keyword)
    except Exception:
        _refund(user, charge, cost)
        raise
    record_search(result)
    return result


def _refund(user, charge, cost):
    try:
        add_tokens(
            user,
            cost,
            reason="Refund: keyword check failed",
            reference=f"refund:{charge.pk}",
            idempotency_key=f"refund-{charge.pk}",
        )
    except Exception:
        logger.exception("Could not refund %s tokens to user %s", cost, user.pk)
