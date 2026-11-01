import threading

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connections
from django.test import Client, TestCase, TransactionTestCase

from apps.tokens import (
    InsufficientTokens,
    InvalidAmount,
    add_tokens,
    consume_tokens,
    get_balance,
    get_transactions,
)
from apps.tokens.models import TokenAccount, TokenTransaction
from apps.core.tests.utils import ADMIN

User = get_user_model()


def make_user(email="u@example.com"):
    return User.objects.create_user(email)


class BasicTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_balance_zero_without_account(self):
        self.assertEqual(get_balance(self.user), 0)
        self.assertFalse(TokenAccount.objects.exists())

    def test_add_and_consume(self):
        add_tokens(self.user, 10, reason="gift")
        tx = consume_tokens(self.user, 3, reason="check", reference="kw:mic")
        self.assertEqual(get_balance(self.user), 7)
        self.assertEqual((tx.kind, tx.amount, tx.balance_after), ("debit", -3, 7))
        self.assertEqual((tx.reason, tx.reference), ("check", "kw:mic"))

    def test_transactions_newest_first_with_filters(self):
        add_tokens(self.user, 10)
        consume_tokens(self.user, 4)
        add_tokens(self.user, 1)
        amounts = [t.amount for t in get_transactions(self.user)]
        self.assertEqual(amounts, [1, -4, 10])
        self.assertEqual([t.amount for t in get_transactions(self.user, kind="debit")], [-4])
        self.assertEqual(len(get_transactions(self.user, limit=2)), 2)

    def test_transactions_are_per_user(self):
        other = make_user("o@example.com")
        add_tokens(other, 5)
        self.assertEqual(get_transactions(self.user).count(), 0)

    def test_ledger_sums_to_balance(self):
        add_tokens(self.user, 20)
        consume_tokens(self.user, 6)
        add_tokens(self.user, 3)
        total = sum(t.amount for t in get_transactions(self.user))
        self.assertEqual(total, get_balance(self.user))

    def test_invalid_amounts(self):
        for bad in (0, -5, 1.5, "3", None, True):
            with self.assertRaises(InvalidAmount):
                add_tokens(self.user, bad)
            with self.assertRaises(InvalidAmount):
                consume_tokens(self.user, bad)
        self.assertEqual(TokenTransaction.objects.count(), 0)

    def test_overdraw_rejected_and_records_nothing(self):
        add_tokens(self.user, 5)
        with self.assertRaises(InsufficientTokens) as ctx:
            consume_tokens(self.user, 6)
        self.assertEqual((ctx.exception.balance, ctx.exception.required), (5, 6))
        self.assertEqual(get_balance(self.user), 5)
        self.assertEqual(TokenTransaction.objects.count(), 1)

    def test_consume_with_no_account_rejected(self):
        with self.assertRaises(InsufficientTokens):
            consume_tokens(self.user, 1)
        self.assertEqual(TokenTransaction.objects.count(), 0)

    def test_exact_balance_can_be_spent(self):
        add_tokens(self.user, 5)
        consume_tokens(self.user, 5)
        self.assertEqual(get_balance(self.user), 0)

    def test_idempotency_key_charges_once(self):
        add_tokens(self.user, 10)
        first = consume_tokens(self.user, 4, idempotency_key="req-1")
        again = consume_tokens(self.user, 4, idempotency_key="req-1")
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(get_balance(self.user), 6)

    def test_db_constraint_blocks_negative_balance(self):
        add_tokens(self.user, 1)
        with self.assertRaises(IntegrityError):
            TokenAccount.objects.filter(user=self.user).update(balance=-1)


class ConcurrencyTests(TransactionTestCase):
    def run_threads(self, targets):
        errors = []

        def wrap(fn):
            def run():
                try:
                    fn()
                except Exception as exc:  # collect everything, assert later
                    errors.append(exc)
                finally:
                    connections.close_all()

            return run

        barrier = threading.Barrier(len(targets))
        threads = []
        for fn in targets:
            def go(fn=fn):
                barrier.wait()
                fn()

            threads.append(threading.Thread(target=wrap(go)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return errors

    def test_simultaneous_consumes_never_overdraw(self):
        user = make_user()
        add_tokens(user, 5)
        results = []

        def spend():
            try:
                consume_tokens(user, 1)
                results.append("ok")
            except InsufficientTokens:
                results.append("short")

        errors = self.run_threads([spend] * 12)
        self.assertEqual(errors, [])
        self.assertEqual(results.count("ok"), 5)
        self.assertEqual(results.count("short"), 7)
        self.assertEqual(get_balance(user), 0)
        self.assertEqual(get_transactions(user, kind="debit").count(), 5)

    def test_one_big_spend_vs_many_small(self):
        user = make_user()
        add_tokens(user, 10)
        outcomes = []

        def spend(n):
            def run():
                try:
                    consume_tokens(user, n)
                    outcomes.append(n)
                except InsufficientTokens:
                    pass

            return run

        errors = self.run_threads([spend(7), spend(7), spend(4), spend(4)])
        self.assertEqual(errors, [])
        self.assertEqual(get_balance(user), 10 - sum(outcomes))
        self.assertGreaterEqual(get_balance(user), 0)

    def test_concurrent_adds_and_consumes_stay_consistent(self):
        user = make_user()
        add_tokens(user, 10)
        targets = [lambda: add_tokens(user, 2)] * 6 + [lambda: _try_consume(user, 3)] * 6
        errors = self.run_threads(targets)
        self.assertEqual(errors, [])
        total = sum(t.amount for t in get_transactions(user))
        self.assertEqual(total, get_balance(user))
        self.assertGreaterEqual(get_balance(user), 0)

    def test_concurrent_first_use_creates_one_account(self):
        user = make_user()
        errors = self.run_threads([lambda: add_tokens(user, 1)] * 8)
        self.assertEqual(errors, [])
        self.assertEqual(TokenAccount.objects.filter(user=user).count(), 1)
        self.assertEqual(get_balance(user), 8)

    def test_concurrent_same_idempotency_key_charges_once(self):
        user = make_user()
        add_tokens(user, 10)
        errors = self.run_threads([lambda: consume_tokens(user, 3, idempotency_key="same")] * 6)
        self.assertEqual(errors, [])
        self.assertEqual(get_balance(user), 7)


def _try_consume(user, n):
    try:
        consume_tokens(user, n)
    except InsufficientTokens:
        pass


class AdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser("boss@example.com")
        self.user = make_user("target@example.com")
        self.client = Client()
        self.client.force_login(self.staff)

    def test_create_account_with_grant(self):
        resp = self.client.post(
            ADMIN + "tokens/tokenaccount/add/",
            {"user": self.user.pk, "adjust_by": 50, "reason": "testing"},
        )
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["errors"])
        self.assertEqual(get_balance(self.user), 50)
        tx = get_transactions(self.user).get()
        self.assertEqual((tx.amount, tx.reason, tx.reference), (50, "testing", "admin:boss@example.com"))

    def test_adjust_existing_account(self):
        add_tokens(self.user, 30)
        acct = TokenAccount.objects.get(user=self.user)
        self.client.post(f"{ADMIN}tokens/tokenaccount/{acct.pk}/change/", {"adjust_by": 20})
        self.assertEqual(get_balance(self.user), 50)
        self.client.post(f"{ADMIN}tokens/tokenaccount/{acct.pk}/change/", {"adjust_by": -10})
        self.assertEqual(get_balance(self.user), 40)

    def test_over_removal_shows_error_and_changes_nothing(self):
        add_tokens(self.user, 5)
        acct = TokenAccount.objects.get(user=self.user)
        resp = self.client.post(f"{ADMIN}tokens/tokenaccount/{acct.pk}/change/", {"adjust_by": -9})
        self.assertContains(resp, "Cannot remove 9 tokens")
        self.assertEqual(get_balance(self.user), 5)

    def test_balance_cannot_be_edited_directly(self):
        add_tokens(self.user, 5)
        acct = TokenAccount.objects.get(user=self.user)
        self.client.post(f"{ADMIN}tokens/tokenaccount/{acct.pk}/change/", {"balance": 999})
        self.assertEqual(get_balance(self.user), 5)

    def test_ledger_is_read_only(self):
        tx = add_tokens(self.user, 5)
        self.assertEqual(self.client.get(ADMIN + "tokens/tokentransaction/").status_code, 200)
        self.assertEqual(self.client.get(ADMIN + "tokens/tokentransaction/add/").status_code, 403)
        self.assertEqual(self.client.post(f"{ADMIN}tokens/tokentransaction/{tx.pk}/delete/").status_code, 403)
        self.assertEqual(self.client.post(f"{ADMIN}tokens/tokentransaction/{tx.pk}/change/", {"amount": 1}).status_code, 403)
        self.assertEqual(TokenTransaction.objects.get(pk=tx.pk).amount, 5)


class TokenPageTests(TestCase):
    def setUp(self):
        self.user = make_user("page@example.com")
        self.client = Client()
        self.client.force_login(self.user)

    def test_requires_login(self):
        resp = Client().get("/tokens/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/accounts/login/?next="))

    def test_empty_state_and_zero_balance(self):
        resp = self.client.get("/tokens/")
        self.assertContains(resp, "No transactions yet")
        self.assertEqual(resp.context["balance"], 0)

    def test_shows_balance_and_history(self):
        add_tokens(self.user, 1500, reason="welcome bonus")
        consume_tokens(self.user, 20, reason="keyword check", reference="kw:mic")
        resp = self.client.get("/tokens/")
        self.assertContains(resp, "1,480")
        self.assertContains(resp, "welcome bonus")
        self.assertContains(resp, "+1,500")
        self.assertContains(resp, "-20")
        self.assertContains(resp, "kw:mic")
        self.assertContains(resp, "My tokens")

    def test_only_own_transactions(self):
        other = make_user("other@example.com")
        add_tokens(other, 99, reason="not yours")
        self.assertNotContains(self.client.get("/tokens/"), "not yours")
        self.assertEqual(self.client.get("/tokens/").context["balance"], 0)

    def test_filter_by_kind_and_ignores_bad_kind(self):
        add_tokens(self.user, 10, reason="gift")
        consume_tokens(self.user, 3, reason="spent")
        debits = self.client.get("/tokens/?kind=debit")
        self.assertContains(debits, "spent")
        self.assertNotContains(debits, "gift")
        self.assertEqual(self.client.get("/tokens/?kind=bogus").status_code, 200)

    def test_pagination(self):
        for i in range(25):
            add_tokens(self.user, 1, reason=f"tx{i}")
        first = self.client.get("/tokens/")
        self.assertEqual(len(first.context["page"]), 20)
        self.assertContains(first, "Page 1 of 2")
        second = self.client.get("/tokens/?page=2")
        self.assertEqual(len(second.context["page"]), 5)
        self.assertEqual(self.client.get("/tokens/?page=abc").status_code, 200)

    def test_navbar_link(self):
        self.assertContains(self.client.get("/"), 'href="/tokens/"')
        self.assertNotContains(Client().get("/"), 'href="/tokens/"')
