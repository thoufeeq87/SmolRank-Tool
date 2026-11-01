from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from apps.core.tests.utils import ADMIN, auth_client

from ..services.analyzer import analyze_payload, check_keyword

SUBS = [1930000, 3530000, 4630, 1930000, 312000, 716000, 3530000, 12300, 216000, 38100]
PAYLOAD = {
    "keyword": "mic",
    "results": [
        {"rank": i + 1, "channel_title": f"c{i}", "video_title": "v", "subscriber_count": s}
        for i, s in enumerate(SUBS)
    ],
}
CHECK = "apps.winnability.clients.smolrank.SmolRankClient.check"


class AnalyzerTests(TestCase):
    def test_winnable_default_threshold(self):
        r = analyze_payload(PAYLOAD, 10000, 10)
        self.assertTrue(r.winnable)
        self.assertEqual([c.subscriber_count for c in r.small_channels], [4630])

    def test_threshold_change_flips_verdict(self):
        self.assertFalse(analyze_payload(PAYLOAD, 1000, 10).winnable)
        self.assertEqual(len(analyze_payload(PAYLOAD, 13000, 10).small_channels), 2)

    def test_threshold_is_strict(self):
        self.assertFalse(analyze_payload(PAYLOAD, 4630, 10).winnable)

    def test_top_n_limits(self):
        self.assertFalse(analyze_payload(PAYLOAD, 10000, 2).winnable)


class ServiceViewTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(SMOLRANK_SUBSCRIBER_THRESHOLD=10000, SMOLRANK_TOP_N=10)
    def test_api_view_and_cache(self):
        with patch(CHECK, return_value=PAYLOAD) as m:
            resp = auth_client().get("/api/check/?keyword=mic")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["winnable"])
            check_keyword("mic")
            self.assertEqual(m.call_count, 1)

    def test_missing_keyword(self):
        self.assertEqual(auth_client().get("/api/check/").status_code, 400)

    def test_html_page(self):
        with patch(CHECK, return_value=PAYLOAD):
            resp = auth_client().get("/results/?keyword=mic")
        self.assertContains(resp, "Winnable")


class ErrorAndCommandTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_bad_shape(self):
        from ..exceptions import SmolRankResponseError

        for bad in ({}, [], {"results": [{"rank": 1}]}, {"results": "x"}):
            with self.assertRaises(SmolRankResponseError):
                analyze_payload(bad, 10000, 10)

    def test_missing_key(self):
        with override_settings(RAPIDAPI_KEY=""):
            resp = auth_client().get("/api/check/?keyword=mic")
        self.assertEqual(resp.status_code, 502)
        self.assertIn("RAPIDAPI_KEY", resp.json()["error"])

    def test_command(self):
        import tempfile
        from pathlib import Path

        from django.core.management import call_command

        out = Path(tempfile.mkdtemp()) / "r.html"
        payload = dict(PAYLOAD, freshness_opportunity=True, suggestions=["mic long tail"])
        with patch(CHECK, return_value=payload):
            call_command("smolrank_page", "mic", "-o", str(out))
        html = out.read_text(encoding="utf-8")
        self.assertIn("1 of the top 10", html)
        self.assertIn("Freshness opportunity", html)
        self.assertIn("mic long tail", html)


class UITests(TestCase):
    def setUp(self):
        cache.clear()

    def test_landing_and_analyze(self):
        self.assertContains(auth_client().get("/"), "Can a small channel rank for this keyword?")
        resp = auth_client().get("/analyze/")
        self.assertContains(resp, 'maxlength="100"')
        self.assertContains(resp, 'name="keyword"')

    def test_too_long_and_empty_show_inline_error(self):
        resp = auth_client().get("/results/?keyword=" + "a" * 101)
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "under 100 characters", status_code=400)
        resp = auth_client().get("/results/?keyword=")
        self.assertContains(resp, "Enter a keyword to check.", status_code=400)

    def test_tough_verdict_and_flags(self):
        payload = dict(PAYLOAD)
        payload["results"] = [
            dict(r, subscriber_count=500000, is_outdated=(r["rank"] == 1), is_outlier=(r["rank"] == 2))
            for r in PAYLOAD["results"]
        ]
        payload["suggestions"] = ["mic for kids"]
        with patch(CHECK, return_value=payload):
            resp = auth_client().get("/results/?keyword=mic")
        self.assertContains(resp, "Tough")
        self.assertContains(resp, "0 of the top 10 channels have under 10,000 subscribers")
        self.assertContains(resp, "OUTDATED")
        self.assertContains(resp, "OUTLIER")
        self.assertContains(resp, "mic%20for%20kids")
        self.assertNotContains(resp, "Freshness opportunity")
        self.assertContains(resp, "Check another keyword")

    def test_error_card(self):
        with override_settings(RAPIDAPI_KEY=""):
            resp = auth_client().get("/results/?keyword=mic")
        self.assertContains(resp, "Something went wrong")
        self.assertContains(resp, "RAPIDAPI_KEY")


class HistoryAdminTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_search_logged_html_and_api(self):
        from ..models import SearchLog

        with patch(CHECK, return_value=PAYLOAD):
            auth_client().get("/results/?keyword=mic")
            auth_client().get("/api/check/?keyword=mic")
        self.assertEqual(SearchLog.objects.count(), 2)
        log = SearchLog.objects.first()
        self.assertTrue(log.winnable)
        self.assertEqual((log.small_count, log.total), (1, 10))

    def test_failed_search_not_logged(self):
        from ..models import SearchLog

        with override_settings(RAPIDAPI_KEY=""):
            auth_client().get("/results/?keyword=mic")
        self.assertEqual(SearchLog.objects.count(), 0)

    def test_logging_failure_does_not_break_page(self):
        with patch(CHECK, return_value=PAYLOAD), patch(
            "apps.winnability.services.history.SearchLog.objects.create", side_effect=RuntimeError
        ):
            self.assertEqual(auth_client().get("/results/?keyword=mic").status_code, 200)

    def test_admin_requires_login_and_lists_logs(self):
        from django.contrib.auth import get_user_model

        self.assertEqual(Client().get(ADMIN).status_code, 302)
        User = get_user_model()
        user = User.objects.create_superuser("root@example.com")
        c = auth_client()
        c.force_login(user)
        self.assertEqual(c.get(ADMIN + "winnability/searchlog/").status_code, 200)


class LoginRequiredTests(TestCase):
    def test_anonymous_redirected_to_login_with_next(self):
        for url in ("/analyze/", "/results/?keyword=mic"):
            resp = Client().get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp["Location"].startswith("/accounts/login/?next="), resp["Location"])

    def test_anonymous_api_gets_401_and_no_api_call(self):
        with patch(CHECK) as m:
            resp = Client().get("/api/check/?keyword=mic")
        self.assertEqual(resp.status_code, 401)
        m.assert_not_called()

    def test_landing_public_and_menu_hidden(self):
        resp = Client().get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'class="font-heading font-bold border-3 border-ink bg-surface px-4 py-1.5')
        self.assertContains(resp, "Log in")

    def test_signed_in_sees_menu(self):
        self.assertContains(auth_client().get("/"), "Log out")
        self.assertEqual(auth_client().get("/analyze/").status_code, 200)
