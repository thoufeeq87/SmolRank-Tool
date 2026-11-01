from django.conf import settings
from django.db import models
from django.db.models import Q


class TokenAccount(models.Model):
    """Current balance per user. Only change it through apps.tokens.api."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="token_account"
    )
    balance = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # last line of defence: the database itself refuses a negative balance
            models.CheckConstraint(condition=Q(balance__gte=0), name="token_balance_non_negative"),
        ]

    def __str__(self):
        return f"{self.user} ({self.balance})"


class TokenTransaction(models.Model):
    """Append-only ledger of every balance change."""

    class Kind(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="token_transactions"
    )
    kind = models.CharField(max_length=6, choices=Kind.choices)
    amount = models.BigIntegerField(help_text="Signed: positive credits, negative debits.")
    balance_after = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user} {self.amount:+d} -> {self.balance_after}"
