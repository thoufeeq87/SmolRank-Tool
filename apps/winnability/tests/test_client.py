from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..clients.smolrank import SmolRankClient
from ..exceptions import SmolRankRateLimitError

GET = "apps.winnability.clients.smolrank.requests.get"


class RateLimitMessageTests(TestCase):
    def make_client(self):
        return SmolRankClient(url="http://x", host="h", key="k", timeout=1)

    def test_uses_api_detail_message(self):
        resp = MagicMock(status_code=429)
        resp.json.return_value = {"detail": "Daily limit of 10 fresh keyword lookups reached."}
        with patch(GET, return_value=resp):
            with self.assertRaisesMessage(SmolRankRateLimitError, "Daily limit of 10 fresh keyword lookups"):
                self.make_client().check("mic")

    def test_falls_back_when_no_detail(self):
        resp = MagicMock(status_code=429)
        resp.json.side_effect = ValueError
        with patch(GET, return_value=resp):
            with self.assertRaisesMessage(SmolRankRateLimitError, "rate limit reached"):
                self.make_client().check("mic")
