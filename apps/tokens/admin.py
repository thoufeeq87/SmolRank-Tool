from django import forms
from django.contrib import admin, messages

from .api import add_tokens, consume_tokens
from .exceptions import InsufficientTokens
from .models import TokenAccount, TokenTransaction


class TokenAccountForm(forms.ModelForm):
    adjust_by = forms.IntegerField(
        required=False,
        help_text="Signed amount: 100 adds 100 tokens, -20 removes 20. Recorded in the ledger.",
    )
    reason = forms.CharField(required=False, max_length=255)

    class Meta:
        model = TokenAccount
        fields = ["user"]

    def clean_adjust_by(self):
        n = self.cleaned_data.get("adjust_by") or 0
        balance = self.instance.balance if self.instance.pk else 0
        if n < 0 and -n > balance:
            raise forms.ValidationError(f"Cannot remove {-n} tokens: balance is only {balance}.")
        return n


@admin.register(TokenAccount)
class TokenAccountAdmin(admin.ModelAdmin):
    form = TokenAccountForm
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)
    fields = ("user", "balance", "adjust_by", "reason")

    def get_readonly_fields(self, request, obj=None):
        # balance is only ever changed through the ledger
        return ("balance", "user") if obj else ("balance",)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        n = form.cleaned_data.get("adjust_by") or 0
        reason = form.cleaned_data.get("reason") or "Admin adjustment"
        reference = f"admin:{request.user.email}"
        try:
            if n > 0:
                add_tokens(obj.user, n, reason=reason, reference=reference)
            elif n < 0:
                consume_tokens(obj.user, -n, reason=reason, reference=reference)
            else:
                TokenAccount.objects.get_or_create(user=obj.user)
        except InsufficientTokens as exc:  # lost a race with a concurrent spend
            self.message_user(request, str(exc), level=messages.ERROR)
        account = TokenAccount.objects.get(user=obj.user)
        obj.pk, obj.balance = account.pk, account.balance


@admin.register(TokenTransaction)
class TokenTransactionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "amount", "balance_after", "reason", "reference")
    list_filter = ("kind", "created_at")
    search_fields = ("user__email", "reference", "reason")
    date_hierarchy = "created_at"
    autocomplete_fields = ("user",)

    # the ledger is append-only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
