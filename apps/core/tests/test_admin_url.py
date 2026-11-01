from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.checks import run_checks
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.settings.security import normalize_admin_url

from .utils import ADMIN


class NormalizeTests(SimpleTestCase):
    def test_default_and_blank(self):
        self.assertEqual(normalize_admin_url(None), "admin/")
        self.assertEqual(normalize_admin_url(""), "admin/")

    def test_slashes_normalised(self):
        for raw in ("secret", "/secret", "secret/", "/secret/", "  secret  "):
            self.assertEqual(normalize_admin_url(raw), "secret/")

    def test_nested_and_symbols_allowed(self):
        self.assertEqual(normalize_admin_url("k3v9-private_x7.Q~m2/panel"), "k3v9-private_x7.Q~m2/panel/")

    def test_invalid_characters_rejected(self):
        for bad in ("has space", "semi;colon", "q?x", "a//b", "../up", "ünï"):
            with self.assertRaises(ImproperlyConfigured, msg=bad):
                normalize_admin_url(bad)

    def test_reserved_paths_rejected(self):
        for bad in ("accounts", "Tokens/x", "billing", "api", "results"):
            with self.assertRaises(ImproperlyConfigured, msg=bad):
                normalize_admin_url(bad)


class AdminUrlRoutingTests(TestCase):
    def test_admin_is_served_at_configured_url(self):
        self.assertEqual(reverse("admin:index"), ADMIN)
        self.assertTrue(ADMIN.startswith("/") and ADMIN.endswith("/"))
        # unauthenticated: redirected into the magic-link login, not a 404
        self.assertEqual(Client().get(ADMIN).status_code, 302)

    def test_default_admin_path_is_gone_when_customised(self):
        if settings.ADMIN_URL == "admin/":
            self.skipTest("ADMIN_URL is the default in this environment")
        self.assertEqual(Client().get("/admin/").status_code, 404)
        self.assertEqual(Client().get("/admin/login/").status_code, 404)

    def test_login_redirect_goes_to_custom_path(self):
        resp = Client().get(ADMIN + "login/?next=" + ADMIN)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/accounts/login/"))


class AdminUrlCheckTests(SimpleTestCase):
    def ids(self):
        return [m.id for m in run_checks(tags=["security"])]

    @override_settings(ADMIN_URL="admin/")
    def test_warns_on_default(self):
        self.assertIn("core.W001", self.ids())

    @override_settings(ADMIN_URL="k3v9-private-x7Qm2pLw/")
    def test_quiet_on_custom(self):
        self.assertNotIn("core.W001", self.ids())
