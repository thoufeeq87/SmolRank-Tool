import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from polar.v2026_10.webhooks import (
    PolarWebhookUnknownTypeError,
    PolarWebhookVerificationError,
    validate_event,
)

from apps.tokens import get_balance

from .exceptions import CheckoutError
from .models import TokenPackage
from .services.checkout import create_checkout_url
from .services.fulfillment import fulfill_paid_order

webhook_logger = logging.getLogger("apps.billing.webhooks")


def _packages():
    return TokenPackage.objects.filter(is_active=True)


class PackagesView(LoginRequiredMixin, View):
    template_name = "billing/packages.html"

    def get(self, request):
        return render(request, self.template_name, {"packages": _packages(), "balance": get_balance(request.user)})


class CheckoutView(LoginRequiredMixin, View):
    """POST only: create a Polar checkout session and send the customer to it."""

    http_method_names = ["post"]

    def post(self, request, package_id):
        package = get_object_or_404(_packages(), pk=package_id)
        try:
            url = create_checkout_url(request.user, package)
        except CheckoutError as exc:
            ctx = {"packages": _packages(), "balance": get_balance(request.user), "error": str(exc)}
            return render(request, PackagesView.template_name, ctx, status=502)
        return redirect(url)


class SuccessView(LoginRequiredMixin, View):
    """Display only. Tokens are credited by the order.paid webhook, never from here."""

    def get(self, request):
        return render(request, "billing/success.html", {"balance": get_balance(request.user)})


class CancelView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "billing/cancel.html")


@csrf_exempt
@require_POST
def polar_webhook(request):
    secret = settings.POLAR_WEBHOOK_SECRET
    webhook_id = request.headers.get("webhook-id", "-")
    if not secret:
        webhook_logger.error("POLAR_WEBHOOK_SECRET is not configured; rejecting webhook %s", webhook_id)
        return HttpResponse(status=500)

    try:
        event = validate_event(request.body, dict(request.headers), secret)
    except PolarWebhookVerificationError:
        webhook_logger.warning("Webhook %s rejected: invalid signature", webhook_id)
        return HttpResponse(status=403)
    except PolarWebhookUnknownTypeError:
        webhook_logger.info("Webhook %s: unknown event type, acknowledged", webhook_id)
        return HttpResponse(status=200)
    except Exception:
        webhook_logger.exception("Webhook %s: could not parse payload", webhook_id)
        return HttpResponse(status=400)

    webhook_logger.info("Webhook %s received: %s", webhook_id, event.type)
    if event.type != "order.paid":
        return HttpResponse(status=200)  # other events are logged, never credited

    try:
        outcome = fulfill_paid_order(event.data)
    except Exception:
        webhook_logger.exception("Webhook %s: failed to process order.paid", webhook_id)
        return HttpResponse(status=500)  # Polar will retry
    webhook_logger.info("Webhook %s order.paid -> %s", webhook_id, outcome)
    return HttpResponse(status=200)
