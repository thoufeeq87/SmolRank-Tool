from django.conf import settings
from django.db import models


class TokenPackage(models.Model):
    """A purchasable bundle of tokens. Managed in the Django admin."""

    name = models.CharField(max_length=100)
    token_amount = models.PositiveIntegerField(help_text="Tokens credited when the order is paid.")
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Shown to users only (USD). The amount actually charged is the price set on the Polar product.",
    )
    polar_product_id = models.CharField(
        max_length=64, help_text="Product ID from the Polar dashboard (sandbox and production differ)."
    )
    is_active = models.BooleanField(default=True, help_text="Inactive packages are hidden from the shop.")
    sort_order = models.PositiveIntegerField(default=0, help_text="Lower numbers are shown first.")

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name} ({self.token_amount} tokens)"


class Order(models.Model):
    """One paid Polar order. polar_order_id is unique, so a replayed webhook can't credit twice."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    package = models.ForeignKey(
        TokenPackage, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    tokens = models.PositiveIntegerField(help_text="Tokens credited for this order.")
    polar_order_id = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.polar_order_id} ({self.user})"
