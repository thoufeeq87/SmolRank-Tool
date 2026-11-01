from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import EmailLoginForm
from .services.magic_links import (
    MagicLinkEmailError,
    MagicLinkRateLimited,
    is_token_valid,
    request_link,
)

SESSION_EMAIL_KEY = "magic_link_email"


def safe_next(request, value):
    """Return `value` only if it points back at this site, else the default landing."""
    if value and url_has_allowed_host_and_scheme(
        value, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return value
    return resolve_url(settings.LOGIN_REDIRECT_URL)


def admin_login(request, extra_context=None):
    """Replaces admin.site.login: send people to the magic-link login page."""
    if request.user.is_authenticated:
        raise PermissionDenied  # signed in, but not staff
    query = urlencode({"next": request.GET.get("next", "")})
    return redirect(f"{resolve_url('accounts:login')}?{query}")


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        next_url = request.GET.get("next", "")
        if request.user.is_authenticated:
            return redirect(safe_next(request, next_url))
        return render(request, self.template_name, {"form": EmailLoginForm(), "next": next_url})

    def post(self, request):
        next_url = request.POST.get("next", "")
        form = EmailLoginForm(request.POST)
        ctx = {"form": form, "next": next_url}
        if not form.is_valid():
            return render(request, self.template_name, ctx, status=400)
        try:
            request_link(form.cleaned_data["email"], safe_next(request, next_url) if next_url else "")
        except MagicLinkEmailError as exc:
            form.add_error("email", str(exc))
            status = 429 if isinstance(exc, MagicLinkRateLimited) else 502
            return render(request, self.template_name, ctx, status=status)
        request.session[SESSION_EMAIL_KEY] = form.cleaned_data["email"]
        return redirect("accounts:sent")


class LinkSentView(View):
    def get(self, request):
        ctx = {
            "email": request.session.get(SESSION_EMAIL_KEY, ""),
            "console_email": "console" in settings.EMAIL_BACKEND.lower(),
        }
        return render(request, "accounts/sent.html", ctx)


class VerifyView(View):
    """GET only shows a confirm button (mail scanners prefetch links); POST signs in."""

    def get(self, request, token):
        if not is_token_valid(token):
            return render(request, "accounts/invalid_link.html", status=400)
        return render(request, "accounts/verify.html", {"token": token, "next": request.GET.get("next", "")})

    def post(self, request, token):
        user = authenticate(request, token=token)
        if user is None:
            return render(request, "accounts/invalid_link.html", status=400)
        login(request, user)
        return redirect(safe_next(request, request.POST.get("next", "")))


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL)
