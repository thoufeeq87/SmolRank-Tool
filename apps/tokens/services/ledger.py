from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ..exceptions import InsufficientTokens
from ..models import TokenAccount, TokenTransaction

CREDIT = TokenTransaction.Kind.CREDIT
DEBIT = TokenTransaction.Kind.DEBIT


def _existing(key):
    return TokenTransaction.objects.filter(idempotency_key=key).first() if key else None


def apply_change(user, amount, kind, *, reason="", reference="", idempotency_key=None):
    """Atomically credit or debit `amount` (a positive int) and write a ledger row.

    The debit check and decrement are ONE conditional UPDATE
    (`... WHERE balance >= amount`), so concurrent requests can never both pass
    a stale balance check. Works on every database, no select_for_update needed.
    """
    if (existing := _existing(idempotency_key)) is not None:
        return existing

    try:
        with transaction.atomic():
            TokenAccount.objects.get_or_create(user_id=user.pk)
            accounts = TokenAccount.objects.filter(user_id=user.pk)
            now = timezone.now()

            if kind == DEBIT:
                changed = accounts.filter(balance__gte=amount).update(
                    balance=F("balance") - amount, updated_at=now
                )
                if not changed:
                    raise InsufficientTokens(accounts.values_list("balance", flat=True).get(), amount)
                signed = -amount
            else:
                accounts.update(balance=F("balance") + amount, updated_at=now)
                signed = amount

            # our UPDATE holds the row lock until commit, so this read is ours
            balance_after = accounts.values_list("balance", flat=True).get()
            return TokenTransaction.objects.create(
                user_id=user.pk,
                kind=kind,
                amount=signed,
                balance_after=balance_after,
                reason=reason,
                reference=reference,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        # a concurrent request with the same idempotency key won the race
        if (existing := _existing(idempotency_key)) is not None:
            return existing
        raise
