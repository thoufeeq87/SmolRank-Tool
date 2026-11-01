from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from apps.tokens import InsufficientTokens, get_balance

from .exceptions import SmolRankAPIError
from .forms import KeywordForm
from .services.billing import run_paid_check, token_cost


def _token_context(user):
    balance = get_balance(user)
    cost = token_cost()
    return {"balance": balance, "cost": cost, "can_afford": balance >= cost}


class LandingView(TemplateView):
    template_name = "winnability/landing.html"


class AnalyzeView(LoginRequiredMixin, View):
    template_name = "winnability/analyze.html"

    def get(self, request):
        return render(request, self.template_name, {"form": KeywordForm(), **_token_context(request.user)})


class ResultsView(LoginRequiredMixin, View):
    template_name = "winnability/results.html"

    def get(self, request):
        form = KeywordForm(request.GET)
        if not form.is_valid():
            # one validation path: show the analyzer again with inline errors
            ctx = {"form": form, **_token_context(request.user)}
            return render(request, AnalyzeView.template_name, ctx, status=400)
        ctx = {"keyword": form.cleaned_data["keyword"]}
        status = 200
        try:
            ctx["result"] = run_paid_check(request.user, ctx["keyword"])
        except InsufficientTokens as exc:
            ctx["insufficient"] = exc
            ctx["cost"] = token_cost()
            status = 402
        except SmolRankAPIError as exc:
            ctx["error"] = str(exc)
        return render(request, self.template_name, ctx, status=status)


class CheckAPIView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "authentication required"}, status=401)
        form = KeywordForm(request.GET)
        if not form.is_valid():
            return JsonResponse({"error": "keyword is required (max 100 characters)"}, status=400)
        try:
            result = run_paid_check(request.user, form.cleaned_data["keyword"])
        except InsufficientTokens as exc:
            return JsonResponse(
                {"error": "insufficient tokens", "balance": exc.balance, "required": exc.required},
                status=402,
            )
        except SmolRankAPIError as exc:
            return JsonResponse({"error": str(exc)}, status=502)
        return JsonResponse(result.to_dict())
