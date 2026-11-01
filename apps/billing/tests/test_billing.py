import base64
import hashlib
import hmac
import json
import threading
import time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from apps.billing.exceptions import BillingConfigError
from apps.billing.models import Order, TokenPackage
from apps.billing.services import polar_client
from apps.tokens import get_balance, get_transactions
from apps.core.tests.utils import ADMIN

User = get_user_model()
VALIDATE = "apps.billing.views.validate_event"
GET_CLIENT = "apps.billing.services.checkout.get_client"
PRODUCT = "11111111-1111-4111-8111-111111111111"


def make_package(**kw):
    defaults = dict(name="Starter", token_amount=300, price=Decimal("5.00"), polar_product_id=PRODUCT)
    return TokenPackage.objects.create(**{**defaults, **kw})


def paid_event(user, package, order_id="ord_1", status="paid", etype="order.paid", metadata="default", **extra):
    """An object shaped like the SDK's WebhookOrderPaidPayload."""
    if metadata == "default":
        metadata = {"user_id": str(user.pk), "package_id": str(package.pk)}
    data = SimpleNamespace(
        id=order_id,
        status=status,
        paid=status == "paid",
        product_id=package.polar_product_id,
        metadata=metadata,
        customer=SimpleNamespace(external_id=str(user.pk)),
        **extra,
    )
    return SimpleNamespace(type=etype, data=data)


def post_webhook(client=None, **headers):
    return (client or Client()).post(
        "/billing/webhook/", data=b"{}", content_type="application/json", **headers
    )


@override_settings(POLAR_WEBHOOK_SECRET="whsec_test")
class WebhookCreditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer@example.com")
        self.package = make_package()

    def deliver(self, event):
        with patch(VALIDATE, return_value=event):
            return post_webhook()

    def test_order_paid_credits_tokens_and_records_order(self):
        resp = self.deliver(paid_event(self.user, self.package))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_balance(self.user), 300)
        order = Order.objects.get()
        self.assertEqual((order.user, order.package, order.tokens, order.polar_order_id, order.status),
                         (self.user, self.package, 300, "ord_1", "paid"))
        tx = get_transactions(self.user).get()
        self.assertEqual((tx.amount, tx.reference), (300, "polar:ord_1"))

    def test_same_event_twice_credits_once(self):
        event = paid_event(self.user, self.package)
        self.assertEqual(self.deliver(event).status_code, 200)
        self.assertEqual(self.deliver(event).status_code, 200)
        self.assertEqual(get_balance(self.user), 300)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(get_transactions(self.user).count(), 1)

    def test_different_orders_both_credit(self):
        self.deliver(paid_event(self.user, self.package, order_id="ord_1"))
        self.deliver(paid_event(self.user, self.package, order_id="ord_2"))
        self.assertEqual(get_balance(self.user), 600)

    def test_other_event_types_are_acknowledged_not_credited(self):
        for etype in ("order.created", "order.updated", "order.refunded", "checkout.created"):
            resp = self.deliver(paid_event(self.user, self.package, etype=etype))
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_balance(self.user), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_unpaid_status_not_credited(self):
        for status in ("pending", "draft", "refunded", "void"):
            self.assertEqual(self.deliver(paid_event(self.user, self.package, status=status)).status_code, 200)
        self.assertEqual(get_balance(self.user), 0)

    def test_pending_then_paid_out_of_order_credits_once(self):
        self.deliver(paid_event(self.user, self.package, status="pending"))
        self.deliver(paid_event(self.user, self.package, status="paid"))
        self.deliver(paid_event(self.user, self.package, status="pending", etype="order.updated"))
        self.assertEqual(get_balance(self.user), 300)

    def test_wrong_product_not_credited(self):
        event = paid_event(self.user, self.package)
        event.data.product_id = "some-other-product"
        self.assertEqual(self.deliver(event).status_code, 200)
        self.assertEqual(get_balance(self.user), 0)

    def test_falls_back_to_external_id_and_product_id_when_metadata_missing(self):
        resp = self.deliver(paid_event(self.user, self.package, metadata={}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_balance(self.user), 300)

    def test_metadata_and_customer_disagreeing_is_refused(self):
        other = User.objects.create_user("other@example.com")
        event = paid_event(self.user, self.package)
        event.data.customer.external_id = str(other.pk)
        self.deliver(event)
        self.assertEqual(get_balance(self.user) + get_balance(other), 0)

    def test_unknown_user_or_package_not_credited(self):
        event = paid_event(self.user, self.package, metadata={"user_id": "99999", "package_id": str(self.package.pk)})
        event.data.customer.external_id = "99999"
        self.assertEqual(self.deliver(event).status_code, 200)
        gone = paid_event(self.user, self.package, order_id="ord_9")
        gone.data.product_id = "ghost"
        self.assertEqual(self.deliver(gone).status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_package_still_credits_a_completed_purchase(self):
        self.package.is_active = False
        self.package.save()
        self.deliver(paid_event(self.user, self.package))
        self.assertEqual(get_balance(self.user), 300)

    def test_processing_failure_returns_500_and_rolls_back_so_retry_works(self):
        event = paid_event(self.user, self.package)
        with patch("apps.billing.services.fulfillment.add_tokens", side_effect=RuntimeError("db down")):
            self.assertEqual(self.deliver(event).status_code, 500)
        self.assertEqual(Order.objects.count(), 0)  # rolled back, so the retry is not seen as a duplicate
        self.assertEqual(self.deliver(event).status_code, 200)
        self.assertEqual(get_balance(self.user), 300)

    def test_events_and_failures_are_logged(self):
        with self.assertLogs("apps.billing.webhooks", level="INFO") as logs:
            self.deliver(paid_event(self.user, self.package))
            self.deliver(paid_event(self.user, self.package))
        text = "\n".join(logs.output)
        self.assertIn("order.paid", text)
        self.assertIn("credited", text)
        self.assertIn("already processed", text)


class WebhookSecurityTests(TestCase):
    secret_key = b"0123456789abcdef0123456789abcdef"
    secret = "whsec_" + base64.b64encode(secret_key).decode()

    def signed_headers(self, body, key=None, msg_id="msg_1"):
        ts = str(int(time.time()))
        sig = hmac.new(key or self.secret_key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()
        return {
            "HTTP_WEBHOOK_ID": msg_id,
            "HTTP_WEBHOOK_TIMESTAMP": ts,
            "HTTP_WEBHOOK_SIGNATURE": "v1," + base64.b64encode(sig).decode(),
        }

    def post(self, body, headers):
        return Client(enforce_csrf_checks=True).post(
            "/billing/webhook/", data=body, content_type="application/json", **headers
        )

    @override_settings(POLAR_WEBHOOK_SECRET=secret)
    def test_valid_signature_is_accepted_without_csrf_token(self):
        body = json.dumps({"type": "some.future.event", "timestamp": "2026-11-01T00:00:00Z", "data": {}}).encode()
        self.assertEqual(self.post(body, self.signed_headers(body)).status_code, 200)

    @override_settings(POLAR_WEBHOOK_SECRET=secret)
    def test_bad_signature_rejected_and_nothing_credited(self):
        user = User.objects.create_user("sig@example.com")
        body = b'{"type": "order.paid"}'
        resp = self.post(body, self.signed_headers(body, key=b"wrong-key-wrong-key-wrong-key-12"))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(get_balance(user), 0)

    @override_settings(POLAR_WEBHOOK_SECRET=secret)
    def test_missing_signature_headers_rejected(self):
        self.assertEqual(self.post(b"{}", {}).status_code, 403)

    @override_settings(POLAR_WEBHOOK_SECRET=secret)
    def test_tampered_body_rejected(self):
        body = b'{"type": "order.paid"}'
        headers = self.signed_headers(body)
        self.assertEqual(self.post(b'{"type": "order.paid", "x": 1}', headers).status_code, 403)

    @override_settings(POLAR_WEBHOOK_SECRET=secret)
    def test_post_only(self):
        for method in ("get", "put", "delete"):
            self.assertEqual(getattr(Client(), method)("/billing/webhook/").status_code, 405)

    @override_settings(POLAR_WEBHOOK_SECRET="")
    def test_unconfigured_secret_fails_closed(self):
        self.assertEqual(post_webhook().status_code, 500)


@override_settings(POLAR_WEBHOOK_SECRET="whsec_test")
class ConcurrentWebhookTests(TransactionTestCase):
    def test_simultaneous_deliveries_of_one_order_credit_once(self):
        user = User.objects.create_user("race@example.com")
        package = make_package()
        event = paid_event(user, package)
        statuses, errors = [], []
        barrier = threading.Barrier(8)

        def deliver():
            try:
                barrier.wait()
                statuses.append(post_webhook().status_code)
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        with patch(VALIDATE, return_value=event):
            threads = [threading.Thread(target=deliver) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertEqual(statuses, [200] * 8)
        self.assertEqual(get_balance(user), 300)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(get_transactions(user).count(), 1)


@override_settings(SITE_URL="https://app.example.com", POLAR_SERVER="sandbox", POLAR_ACCESS_TOKEN="polar_oat_x")
class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper@example.com")
        self.package = make_package()
        self.client = Client()
        self.client.force_login(self.user)

    def fake_client(self, url="https://sandbox.polar.sh/checkout/abc"):
        polar = MagicMock()
        polar.checkouts.create.return_value = SimpleNamespace(url=url, id="chk_1")
        return polar

    def test_requires_login(self):
        resp = Client().post(f"/billing/checkout/{self.package.pk}/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/accounts/login/"))

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(f"/billing/checkout/{self.package.pk}/").status_code, 405)

    def test_creates_session_with_user_and_package_and_redirects(self):
        polar = self.fake_client()
        with patch(GET_CLIENT, return_value=polar):
            resp = self.client.post(f"/billing/checkout/{self.package.pk}/")
        self.assertRedirects(resp, "https://sandbox.polar.sh/checkout/abc", fetch_redirect_response=False)
        kwargs = polar.checkouts.create.call_args.kwargs
        self.assertEqual(kwargs["products"], [PRODUCT])
        self.assertEqual(kwargs["external_customer_id"], str(self.user.pk))
        self.assertEqual(kwargs["metadata"], {"user_id": str(self.user.pk), "package_id": str(self.package.pk)})
        self.assertEqual(kwargs["customer_email"], "shopper@example.com")
        self.assertEqual(kwargs["success_url"], "https://app.example.com/billing/success/?checkout_id={CHECKOUT_ID}")
        self.assertEqual(kwargs["return_url"], "https://app.example.com/billing/cancel/")

    def test_checkout_does_not_credit_tokens(self):
        with patch(GET_CLIENT, return_value=self.fake_client()):
            self.client.post(f"/billing/checkout/{self.package.pk}/")
        self.assertEqual(get_balance(self.user), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_or_missing_package_404(self):
        self.package.is_active = False
        self.package.save()
        self.assertEqual(self.client.post(f"/billing/checkout/{self.package.pk}/").status_code, 404)
        self.assertEqual(self.client.post("/billing/checkout/9999/").status_code, 404)

    def test_sdk_error_shows_error_card(self):
        polar = MagicMock()
        polar.checkouts.create.side_effect = RuntimeError("polar down")
        with patch(GET_CLIENT, return_value=polar):
            resp = self.client.post(f"/billing/checkout/{self.package.pk}/")
        self.assertContains(resp, "couldn&#x27;t start the checkout", status_code=502)

    @override_settings(POLAR_ACCESS_TOKEN="")
    def test_missing_token_shows_friendly_error_not_a_crash(self):
        resp = self.client.post(f"/billing/checkout/{self.package.pk}/")
        self.assertContains(resp, "Payments are not available", status_code=502)

    def test_packages_page_lists_only_active_in_order(self):
        make_package(name="Big", token_amount=3000, sort_order=2)
        make_package(name="Hidden", is_active=False)
        make_package(name="Mid", token_amount=900, sort_order=1)
        content = self.client.get("/billing/").content.decode()
        self.assertNotIn("Hidden", content)
        self.assertLess(content.index("Starter"), content.index("Mid"))
        self.assertLess(content.index("Mid"), content.index("Big"))

    def test_success_page_never_credits(self):
        resp = self.client.get("/billing/success/?checkout_id=chk_1")
        self.assertContains(resp, "Thank you")
        self.assertEqual(get_balance(self.user), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_cancel_page(self):
        self.assertContains(self.client.get("/billing/cancel/"), "Checkout cancelled")

    def test_pages_require_login(self):
        for url in ("/billing/", "/billing/success/", "/billing/cancel/"):
            self.assertEqual(Client().get(url).status_code, 302)


class PolarClientTests(TestCase):
    @override_settings(POLAR_SERVER="sandbox", POLAR_ACCESS_TOKEN="tok")
    def test_sandbox_by_default_setting(self):
        with patch.object(polar_client, "Polar") as polar:
            polar_client.get_client()
        polar.assert_called_once_with("tok", environment="sandbox")

    @override_settings(POLAR_SERVER="production", POLAR_ACCESS_TOKEN="tok")
    def test_production_is_one_setting_change(self):
        with patch.object(polar_client, "Polar") as polar:
            polar_client.get_client()
        polar.assert_called_once_with("tok", environment="production")

    @override_settings(POLAR_SERVER="staging", POLAR_ACCESS_TOKEN="tok")
    def test_invalid_server_rejected(self):
        with self.assertRaises(BillingConfigError):
            polar_client.get_client()

    @override_settings(POLAR_SERVER="sandbox", POLAR_ACCESS_TOKEN="")
    def test_missing_token_rejected(self):
        with self.assertRaises(BillingConfigError):
            polar_client.get_client()

    def test_default_server_setting_is_sandbox(self):
        from config.settings import billing

        self.assertEqual(billing.POLAR_SERVER, "sandbox")


class AdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.client.force_login(User.objects.create_superuser("boss@example.com"))

    def test_package_admin_add_edit_toggle(self):
        resp = self.client.post(
            ADMIN + "billing/tokenpackage/add/",
            {"name": "Pro", "token_amount": 1000, "price": "9.99", "polar_product_id": PRODUCT,
             "is_active": "on", "sort_order": 1},
        )
        self.assertEqual(resp.status_code, 302)
        package = TokenPackage.objects.get()
        self.assertTrue(package.is_active)
        self.client.post(
            f"{ADMIN}billing/tokenpackage/{package.pk}/change/",
            {"name": "Pro", "token_amount": 1000, "price": "9.99", "polar_product_id": PRODUCT, "sort_order": 1},
        )
        package.refresh_from_db()
        self.assertFalse(package.is_active)  # checkbox omitted = turned off
        self.assertEqual(self.client.get(ADMIN + "billing/tokenpackage/?is_active__exact=1").status_code, 200)

    def test_orders_are_read_only(self):
        user = User.objects.create_user("o@example.com")
        order = Order.objects.create(user=user, tokens=5, polar_order_id="ord_x", status="paid")
        self.assertEqual(self.client.get(ADMIN + "billing/order/").status_code, 200)
        self.assertEqual(self.client.get(f"{ADMIN}billing/order/{order.pk}/change/").status_code, 200)  # view-only
        self.assertEqual(self.client.get(ADMIN + "billing/order/add/").status_code, 403)
        self.assertEqual(self.client.post(f"{ADMIN}billing/order/{order.pk}/delete/").status_code, 403)
        self.client.post(f"{ADMIN}billing/order/{order.pk}/change/", {"tokens": 999})
        order.refresh_from_db()
        self.assertEqual(order.tokens, 5)

    def test_duplicate_polar_order_id_rejected_by_database(self):
        from django.db import IntegrityError, transaction

        user = User.objects.create_user("d@example.com")
        Order.objects.create(user=user, tokens=1, polar_order_id="dup", status="paid")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(user=user, tokens=1, polar_order_id="dup", status="paid")
