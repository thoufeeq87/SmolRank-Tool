from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from .api import get_balance, get_transactions
from .models import TokenTransaction

PAGE_SIZE = 20
FILTERS = [("", "All"), ("credit", "Credits"), ("debit", "Debits")]


class TokenPageView(LoginRequiredMixin, View):
    """Signed-in user's balance and transaction history (?kind=credit|debit, ?page=N)."""

    template_name = "tokens/tokens.html"

    def get(self, request):
        kind = request.GET.get("kind")
        if kind not in TokenTransaction.Kind.values:
            kind = None
        page = Paginator(get_transactions(request.user, kind=kind), PAGE_SIZE).get_page(
            request.GET.get("page")
        )
        return render(
            request,
            self.template_name,
            {
                "balance": get_balance(request.user),
                "page": page,
                "kind": kind or "",
                "filters": FILTERS,
            },
        )
