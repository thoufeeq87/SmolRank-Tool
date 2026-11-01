import importlib
import os
import sys
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase

GOOD_KEY = "k" * 64


def load_prod(env):
    """Import config.settings.prod fresh under a controlled environment."""
    sys.modules.pop("config.settings.prod", None)
    with patch.dict(os.environ, env, clear=False):
        for name in ("DJANGO_SECRET_KEY", "DJANGO_BEHIND_PROXY"):
            if name not in env:
                os.environ.pop(name, None)
        try:
            return importlib.import_module("config.settings.prod")
        finally:
            sys.modules.pop("config.settings.prod", None)


class SecurityHeaderTests(TestCase):
    def test_pages_cannot_be_framed(self):
        for url in ("/", "/accounts/login/", "/nope/"):
            self.assertEqual(Client().get(url)["X-Frame-Options"], "DENY", url)

    def test_other_security_headers_present(self):
        resp = Client().get("/")
        self.assertEqual(resp["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resp["Referrer-Policy"], "same-origin")  # keeps magic-link tokens out of Referer headers


class ProdSettingsTests(SimpleTestCase):
    def test_refuses_missing_key(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
            load_prod({})

    def test_refuses_short_key(self):
        with self.assertRaises(ImproperlyConfigured):
            load_prod({"DJANGO_SECRET_KEY": "x" * 49})

    def test_refuses_insecure_prefixed_key(self):
        with self.assertRaises(ImproperlyConfigured):
            load_prod({"DJANGO_SECRET_KEY": "django-insecure-" + "a" * 60})

    def test_accepts_strong_key_and_hardens_transport(self):
        prod = load_prod({"DJANGO_SECRET_KEY": GOOD_KEY, "DJANGO_ALLOWED_HOSTS": "a.example.com, b.example.com"})
        self.assertEqual(prod.SECRET_KEY, GOOD_KEY)
        self.assertFalse(prod.DEBUG)
        self.assertTrue(prod.SESSION_COOKIE_SECURE and prod.CSRF_COOKIE_SECURE and prod.SECURE_SSL_REDIRECT)
        self.assertGreater(prod.SECURE_HSTS_SECONDS, 0)
        self.assertEqual(prod.ALLOWED_HOSTS, ["a.example.com", "b.example.com"])

    def test_proxy_header_is_opt_in(self):
        self.assertFalse(hasattr(load_prod({"DJANGO_SECRET_KEY": GOOD_KEY}), "SECURE_PROXY_SSL_HEADER"))
        behind = load_prod({"DJANGO_SECRET_KEY": GOOD_KEY, "DJANGO_BEHIND_PROXY": "True"})
        self.assertEqual(behind.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))


class DevDebugDefaultTests(SimpleTestCase):
    def load_dev(self, env):
        sys.modules.pop("config.settings.dev", None)
        with patch.dict(os.environ, env, clear=False):
            for name in ("DJANGO_DEBUG", "DJANGO_ALLOWED_HOSTS"):
                if name not in env:
                    os.environ.pop(name, None)
            try:
                return importlib.import_module("config.settings.dev")
            finally:
                sys.modules.pop("config.settings.dev", None)

    def test_debug_on_by_default_locally(self):
        self.assertTrue(self.load_dev({}).DEBUG)

    def test_debug_off_when_a_tunnel_host_is_set(self):
        self.assertFalse(self.load_dev({"DJANGO_ALLOWED_HOSTS": "x.trycloudflare.com"}).DEBUG)

    def test_explicit_debug_setting_still_wins(self):
        dev = self.load_dev({"DJANGO_ALLOWED_HOSTS": "x.trycloudflare.com", "DJANGO_DEBUG": "True"})
        self.assertTrue(dev.DEBUG)
