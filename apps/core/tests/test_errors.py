from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from .utils import auth_client


@override_settings(DEBUG=False)
class ErrorPageTests(TestCase):
    def test_404(self):
        resp = Client().get("/no-such-page/")
        self.assertContains(resp, "Page not found", status_code=404)
        self.assertContains(resp, "Back to home", status_code=404)

    def test_500(self):
        client = auth_client(raise_request_exception=False)
        with patch("apps.winnability.services.billing.check_keyword", side_effect=RuntimeError("boom")):
            resp = client.get("/results/?keyword=mic")
        self.assertContains(resp, "Something broke on our end", status_code=500)
        self.assertNotContains(resp, "{%", status_code=500)
        self.assertNotContains(resp, "boom", status_code=500)
