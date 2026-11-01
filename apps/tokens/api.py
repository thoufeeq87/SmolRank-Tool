"""Public token API. Use `from apps.tokens import ...` anywhere in the project."""
from .exceptions import InvalidAmount
from .models import TokenAccount, TokenTransaction
from .services.ledger import CREDIT, DEBIT, apply_change


def _check_amount(amount):
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise InvalidAmount("Amount must be a positive integer.")


def add_tokens(user, amount, *, reason="", reference="", idempotency_key=None):
    """Credit `amount` tokens. Returns the ledger TokenTransaction."""
    _check_amount(amount)
    return apply_change(
        user, amount, CREDIT, reason=reason, reference=reference, idempotency_key=idempotency_key
    )


def consume_tokens(user, amount, *, reason="", reference="", idempotency_key=None):
    """Debit `amount` tokens. Raises InsufficientTokens (and records nothing) if short."""
    _check_amount(amount)
    return apply_change(
        user, amount, DEBIT, reason=reason, reference=reference, idempotency_key=idempotency_key
    )


def get_balance(user):
    """Current balance; 0 if the user has no account yet."""
    return (
        TokenAccount.objects.filter(user_id=user.pk).values_list("balance", flat=True).first() or 0
    )


def get_transactions(user, *, kind=None, limit=None):
    """The user's ledger, newest first. `kind` is "credit" or "debit"."""
    qs = TokenTransaction.objects.filter(user_id=user.pk)
    if kind:
        qs = qs.filter(kind=kind)
    return qs[:limit] if limit else qs
