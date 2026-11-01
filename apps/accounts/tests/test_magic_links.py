import hashlib
import re
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from ..email_backends.resend import ResendEmailBackend, ResendError
from ..models import MagicLink
from ..services import magic_links
from apps.core.tests.utils import ADMIN

User = get_user_model()


def sent_token():
    """Pull the raw token out of the last outbox email."""
    return re.search(r"/accounts/verify/([^/?\s]+)/", mail.outbox[-1].body).group(1)


class ModelTests(TestCase):
    def test_no_password_field(self):
        self.assertNotIn("password", [f.name for f in User._meta.get_fields()])

    def test_create_user_without_password(self):
        user = User.objects.create_user("A@Example.com")
        self.assertEqual(user.email, "a@example.com")


class RequestLinkTests(TestCase):
    def post_email(self, email="new@example.com", **extra):
        return Client().post("/accounts/login/", {"email": email, **extra})

    def test_new_email_creates_user_and_sends_one_email(self):
        resp = self.post_email()
        self.assertRedirects(resp, "/accounts/sent/")
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.com"])
        self.assertTrue(mail.outbox[0].alternatives)

    def test_existing_email_reuses_user(self):
        self.post_email()
        self.post_email("NEW@example.com")
        self.assertEqual(User.objects.count(), 1)

    def test_token_stored_hashed(self):
        self.post_email()
        token = sent_token()
        link = MagicLink.objects.get()
        self.assertEqual(link.token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn(token, link.token_hash)

    def test_expiry_is_15_minutes(self):
        self.post_email()
        link = MagicLink.objects.get()
        self.assertAlmostEqual((link.expires_at - link.created_at).total_seconds(), 900, delta=5)

    def test_invalid_email_inline_error(self):
        resp = self.post_email("nope")
        self.assertContains(resp, "Enter a valid email address.", status_code=400)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(MAGIC_LINK_MAX_PER_HOUR=2)
    def test_rate_limit_tells_user_how_long_to_wait(self):
        for _ in range(2):
            self.assertRedirects(self.post_email(), "/accounts/sent/")
        resp = self.post_email()
        self.assertContains(resp, "Too many sign-in links requested", status_code=429)
        self.assertContains(resp, "try again in 60 minutes", status_code=429)
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(MAGIC_LINK_MAX_PER_HOUR=2)
    def test_rate_limit_frees_up_as_old_links_age(self):
        for _ in range(2):
            self.post_email()
        oldest = MagicLink.objects.order_by("created_at").first()
        MagicLink.objects.filter(pk=oldest.pk).update(created_at=timezone.now() - timedelta(minutes=50))
        resp = self.post_email()
        self.assertContains(resp, "try again in 10 minutes", status_code=429)
        MagicLink.objects.filter(pk=oldest.pk).update(created_at=timezone.now() - timedelta(minutes=61))
        self.assertRedirects(self.post_email(), "/accounts/sent/")

    def test_inactive_user_gets_no_email(self):
        User.objects.create_user("off@example.com", is_active=False)
        self.post_email("off@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_email_failure_shows_error(self):
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=RuntimeError("smtp down")):
            resp = self.post_email()
        self.assertContains(resp, "send the email", status_code=502)


class VerifyTests(TestCase):
    def setUp(self):
        Client().post("/accounts/login/", {"email": "me@example.com"})
        self.token = sent_token()
        self.url = f"/accounts/verify/{self.token}/"

    def test_get_does_not_consume_or_login(self):
        c = Client()
        self.assertContains(c.get(self.url), "Sign me in")
        self.assertNotIn("_auth_user_id", c.session)
        self.assertIsNone(MagicLink.objects.get().used_at)

    def test_post_logs_in_once_only(self):
        c = Client()
        resp = c.post(self.url)
        self.assertRedirects(resp, "/analyze/", fetch_redirect_response=False)
        self.assertIn("_auth_user_id", c.session)
        second = Client()
        self.assertEqual(second.post(self.url).status_code, 400)
        self.assertNotIn("_auth_user_id", second.session)
        self.assertEqual(second.get(self.url).status_code, 400)

    def test_expired_token_fails(self):
        MagicLink.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        c = Client()
        self.assertEqual(c.post(self.url).status_code, 400)
        self.assertNotIn("_auth_user_id", c.session)

    def test_tampered_token_fails(self):
        c = Client()
        self.assertEqual(c.post(f"/accounts/verify/{self.token}x/").status_code, 400)

    def test_consume_is_single_use_at_service_level(self):
        self.assertIsNotNone(magic_links.consume_token(self.token))
        self.assertIsNone(magic_links.consume_token(self.token))

    def test_next_redirect(self):
        resp = Client().post(self.url, {"next": "/results/?keyword=mic"})
        self.assertRedirects(resp, "/results/?keyword=mic", fetch_redirect_response=False)

    def test_open_redirect_blocked(self):
        for evil in ("https://evil.example/", "//evil.example/"):
            Client().post("/accounts/login/", {"email": "me@example.com"})
            resp = Client().post(f"/accounts/verify/{sent_token()}/", {"next": evil})
            self.assertEqual(resp["Location"], "/analyze/")

    def test_logout_requires_post(self):
        c = Client()
        c.post(self.url)
        self.assertEqual(c.get("/accounts/logout/").status_code, 405)
        c.post("/accounts/logout/")
        self.assertNotIn("_auth_user_id", c.session)


class AdminTests(TestCase):
    def test_admin_login_redirects_to_magic_login(self):
        resp = Client().get(ADMIN + "login/?next=" + ADMIN)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/accounts/login/"))

    def test_non_staff_forbidden(self):
        c = Client()
        c.force_login(User.objects.create_user("plain@example.com"))
        self.assertEqual(c.get(ADMIN + "login/").status_code, 403)

    def test_staff_can_open_admin(self):
        c = Client()
        c.force_login(User.objects.create_superuser("boss@example.com"))
        self.assertEqual(c.get(ADMIN + "accounts/user/").status_code, 200)
        self.assertEqual(c.get(ADMIN + "accounts/user/add/").status_code, 200)

    def test_create_admin_command(self):
        from django.core.management import call_command

        call_command("create_admin", "Boss@Example.com")
        user = User.objects.get(email="boss@example.com")
        self.assertTrue(user.is_staff and user.is_superuser)


@override_settings(RESEND_API_KEY="re_test", DEFAULT_FROM_EMAIL="SmolRank <hi@example.com>")
class ResendBackendTests(TestCase):
    def message(self):
        msg = mail.EmailMultiAlternatives("Subj", "text body", to=["a@example.com"])
        msg.attach_alternative("<b>html</b>", "text/html")
        return msg

    @patch("apps.accounts.email_backends.resend.requests.post")
    def test_payload(self, post):
        post.return_value = MagicMock(status_code=200)
        self.assertEqual(ResendEmailBackend().send_messages([self.message()]), 1)
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.resend.com/emails")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")
        self.assertEqual(
            kwargs["json"],
            {
                "from": "SmolRank <hi@example.com>",
                "to": ["a@example.com"],
                "subject": "Subj",
                "text": "text body",
                "html": "<b>html</b>",
            },
        )

    @patch("apps.accounts.email_backends.resend.requests.post")
    def test_error_status_raises(self, post):
        post.return_value = MagicMock(status_code=403, text="bad domain")
        with self.assertRaisesMessage(ResendError, "403"):
            ResendEmailBackend().send_messages([self.message()])

    @override_settings(RESEND_API_KEY="")
    def test_missing_key(self):
        with self.assertRaises(ImproperlyConfigured):
            ResendEmailBackend().send_messages([self.message()])


class ConsoleBackendTests(TestCase):
    def test_prints_unwrapped_link(self):
        from io import StringIO

        from ..email_backends.console import ConsoleEmailBackend

        link = "http://localhost:8000/accounts/verify/" + "a" * 60 + "/"
        out = StringIO()
        msg = mail.EmailMessage("Subj", f"Open:\n{link}\n", to=["a@example.com"])
        ConsoleEmailBackend(stream=out).send_messages([msg])
        self.assertIn(f"\n{link}\n", out.getvalue())
        self.assertNotIn("=\n", out.getvalue())
