import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.tokens.api import get_balance, get_transactions

from ..services import magic_links

User = get_user_model()


def new_link(email):
    Client().post("/accounts/login/", {"email": email})
    return re.search(r"/accounts/verify/([^/?\s]+)/", mail.outbox[-1].body).group(1)


@override_settings(SIGNUP_BONUS_TOKENS=300)
class SignupBonusTests(TestCase):
    def test_requesting_a_link_alone_gives_nothing(self):
        new_link("fresh@example.com")
        user = User.objects.get(email="fresh@example.com")
        self.assertEqual(get_balance(user), 0)

    def test_first_verified_login_gives_300_once(self):
        Client().post(f"/accounts/verify/{new_link('fresh@example.com')}/")
        user = User.objects.get(email="fresh@example.com")
        self.assertEqual(get_balance(user), 300)
        rows = list(get_transactions(user))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].reason, "Welcome bonus")

    def test_later_logins_do_not_give_more(self):
        for _ in range(3):
            Client().post(f"/accounts/verify/{new_link('fresh@example.com')}/")
        self.assertEqual(get_balance(User.objects.get(email="fresh@example.com")), 300)

    def test_disabled_with_zero(self):
        with override_settings(SIGNUP_BONUS_TOKENS=0):
            Client().post(f"/accounts/verify/{new_link('fresh@example.com')}/")
        self.assertEqual(get_balance(User.objects.get(email="fresh@example.com")), 0)

    def test_inactive_user_gets_nothing(self):
        token = new_link("fresh@example.com")
        User.objects.filter(email="fresh@example.com").update(is_active=False)
        self.assertIsNone(magic_links.consume_token(token))
        self.assertEqual(get_balance(User.objects.get(email="fresh@example.com")), 0)

    def test_grant_failure_never_blocks_sign_in(self):
        token = new_link("fresh@example.com")
        with patch("apps.accounts.services.magic_links.add_tokens", side_effect=RuntimeError("db down")):
            user = magic_links.consume_token(token)
        self.assertIsNotNone(user)
        # the next sign-in retries and succeeds
        Client().post(f"/accounts/verify/{new_link('fresh@example.com')}/")
        self.assertEqual(get_balance(user), 300)
