import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from apps.tokens import InsufficientTokens, add_tokens, get_balance, get_transactions

from ..exceptions import SmolRankAPIError
from ..models import SearchLog
from ..services.billing import run_paid_check

User = get_user_model()
CHECK = "apps.winnability.clients.smolrank.SmolRankClient.check"
PAYLOAD = {
    "keyword": "mic",
    "results": [{"rank": 1, "channel_title": "c", "video_title": "v", "subscriber_count": 100}],
}


def funded_client(tokens, email="payer@example.com"):
    user = User.objects.create_user(email)
    if tokens:
        add_tokens(user, tokens)
    client = Client()
    client.force_login(user)
    return client, user


class ChargeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_default_cost_is_30(self):
        from django.conf import settings

        self.assertEqual(settings.SMOLRANK_TOKEN_COST, 30)

    def test_successful_check_charges_30(self):
        client, user = funded_client(100)
        with patch(CHECK, return_value=PAYLOAD):
            resp = client.get("/results/?keyword=mic")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(get_balance(user), 70)
        debit = get_transactions(user, kind="debit").get()
        self.assertEqual((debit.amount, debit.reason, debit.reference), (-30, "Keyword check", "check:mic"))
        self.assertEqual(SearchLog.objects.count(), 1)

    @override_settings(SMOLRANK_TOKEN_COST=5)
    def test_cost_is_configurable(self):
        client, user = funded_client(100)
        with patch(CHECK, return_value=PAYLOAD):
            client.get("/results/?keyword=mic")
        self.assertEqual(get_balance(user), 95)

    def test_insufficient_tokens_blocks_without_calling_api_or_charging(self):
        client, user = funded_client(29)
        with patch(CHECK, return_value=PAYLOAD) as api:
            resp = client.get("/results/?keyword=mic")
        self.assertContains(resp, "Not enough tokens", status_code=402)
        self.assertContains(resp, "costs 30 tokens", status_code=402)
        api.assert_not_called()
        self.assertEqual(get_balance(user), 29)
        self.assertEqual(SearchLog.objects.count(), 0)

    def test_no_account_cannot_check(self):
        client, user = funded_client(0)
        with patch(CHECK, return_value=PAYLOAD) as api:
            self.assertEqual(client.get("/results/?keyword=mic").status_code, 402)
        api.assert_not_called()

    def test_exact_balance_allows_one_check(self):
        client, user = funded_client(30)
        with patch(CHECK, return_value=PAYLOAD):
            self.assertEqual(client.get("/results/?keyword=mic").status_code, 200)
            self.assertEqual(client.get("/results/?keyword=mic2").status_code, 402)
        self.assertEqual(get_balance(user), 0)

    def test_api_failure_refunds(self):
        client, user = funded_client(100)
        with patch(CHECK, side_effect=SmolRankAPIError("down")):
            resp = client.get("/results/?keyword=mic")
        self.assertContains(resp, "Something went wrong")
        self.assertEqual(get_balance(user), 100)
        refund = get_transactions(user, kind="credit").first()
        self.assertEqual(refund.amount, 30)
        self.assertIn("Refund", refund.reason)
        self.assertEqual(SearchLog.objects.count(), 0)

    def test_unexpected_crash_refunds_too(self):
        user = User.objects.create_user("c@example.com")
        add_tokens(user, 100)
        with patch(CHECK, side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                run_paid_check(user, "mic")
        self.assertEqual(get_balance(user), 100)

    def test_missing_key_refunds(self):
        client, user = funded_client(100)
        with override_settings(RAPIDAPI_KEY=""):
            resp = client.get("/results/?keyword=mic")
        self.assertContains(resp, "RAPIDAPI_KEY")
        self.assertEqual(get_balance(user), 100)

    def test_invalid_keyword_not_charged(self):
        client, user = funded_client(100)
        client.get("/results/?keyword=")
        client.get("/results/?keyword=" + "a" * 101)
        self.assertEqual(get_balance(user), 100)

    def test_cached_check_still_charges(self):
        client, user = funded_client(100)
        with patch(CHECK, return_value=PAYLOAD) as api:
            client.get("/results/?keyword=mic")
            client.get("/results/?keyword=mic")
        self.assertEqual(api.call_count, 1)
        self.assertEqual(get_balance(user), 40)

    def test_api_endpoint_charges_and_returns_402(self):
        client, user = funded_client(40)
        with patch(CHECK, return_value=PAYLOAD):
            self.assertEqual(client.get("/api/check/?keyword=mic").status_code, 200)
            resp = client.get("/api/check/?keyword=mic")
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json(), {"error": "insufficient tokens", "balance": 10, "required": 30})

    def test_api_endpoint_failure_refunds(self):
        client, user = funded_client(40)
        with patch(CHECK, side_effect=SmolRankAPIError("down")):
            self.assertEqual(client.get("/api/check/?keyword=mic").status_code, 502)
        self.assertEqual(get_balance(user), 40)

    def test_analyze_page_shows_cost_and_balance(self):
        client, _ = funded_client(100)
        resp = client.get("/analyze/")
        self.assertContains(resp, "Each check costs 30 tokens")
        self.assertContains(resp, "<strong>100</strong>")
        poor, _ = funded_client(5, "poor@example.com")
        self.assertContains(poor.get("/analyze/"), "You need more tokens")

    def test_management_command_is_not_charged(self):
        from django.core.management import call_command

        user = User.objects.create_user("cli@example.com")
        add_tokens(user, 100)
        out = Path(tempfile.mkdtemp()) / "o.html"
        with patch(CHECK, return_value=PAYLOAD):
            call_command("smolrank_page", "mic", "-o", str(out))
        self.assertEqual(get_balance(user), 100)


class ConcurrentChargeTests(TransactionTestCase):
    def test_simultaneous_checks_cannot_overspend(self):
        cache.clear()
        user = User.objects.create_user("race@example.com")
        add_tokens(user, 90)  # enough for exactly 3 checks
        outcomes, errors = [], []
        barrier = threading.Barrier(8)

        def attempt(i):
            try:
                barrier.wait()
                run_paid_check(user, f"kw{i}")
                outcomes.append("ok")
            except InsufficientTokens:
                outcomes.append("short")
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        with patch(CHECK, return_value=PAYLOAD):
            threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)
        self.assertEqual(errors, [])
        self.assertEqual(outcomes.count("ok"), 3)
        self.assertEqual(outcomes.count("short"), 5)
        self.assertEqual(get_balance(user), 0)
