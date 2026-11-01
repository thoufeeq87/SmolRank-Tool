import os
import runpy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse, set_script_prefix

from config.settings import prefix


def _load(value):
    env = {"DJANGO_URL_PREFIX": value} if value is not None else {}
    with mock.patch.dict(os.environ, env, clear=False):
        if value is None:
            os.environ.pop("DJANGO_URL_PREFIX", None)
        return SimpleNamespace(**runpy.run_path(prefix.__file__))


class PrefixSettingsTests(SimpleTestCase):
    def tearDown(self):
        _load(None)

    def test_unset_means_root(self):
        mod = _load(None)
        self.assertEqual(mod.URL_PREFIX, "")
        self.assertFalse(hasattr(mod, "FORCE_SCRIPT_NAME"))

    def test_prefix_is_normalised_and_scopes_cookies(self):
        for raw in ("smolrank", "/smolrank", "/smolrank/"):
            mod = _load(raw)
            self.assertEqual(mod.FORCE_SCRIPT_NAME, "/smolrank")
            self.assertEqual(mod.SESSION_COOKIE_PATH, "/smolrank")
            self.assertEqual(mod.CSRF_COOKIE_PATH, "/smolrank")


class PrefixedLinksTests(TestCase):
    def tearDown(self):
        set_script_prefix("/")

    @override_settings(FORCE_SCRIPT_NAME="/smolrank")
    def test_links_carry_the_prefix_and_proxy_stripped_paths_resolve(self):
        set_script_prefix("/smolrank/")
        self.assertEqual(reverse("winnability:analyze"), "/smolrank/analyze/")
        # The proxy strips /smolrank, so Django receives the plain path and links come back prefixed.
        response = self.client.get("/")
        self.assertContains(response, 'href="/smolrank/analyze/"')
