from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from apps.smolrank.services.analyzer import build_report, check_keyword
from apps.smolrank.services.exceptions import APIError

PAYLOAD = {"results": [{"channel_name": f"c{i}", "subscribers": s}
                       for i, s in enumerate([500000, 12000, 9999, "2,000"], 1)]}


class AnalyzerTests(SimpleTestCase):
    def test_threshold_is_strictly_under(self):
        r = build_report("x", {"results": [{"channel_name": "a", "subscribers": 10000}]}, threshold=10000)
        self.assertFalse(r.winnable)

    def test_finds_small_channels(self):
        r = build_report("x", PAYLOAD, threshold=10000)
        self.assertTrue(r.winnable)
        self.assertEqual([c.rank for c in r.small_channels], [3, 4])

    @override_settings(SMOLRANK_SUBSCRIBER_THRESHOLD=1000)
    def test_threshold_read_from_settings(self):
        self.assertFalse(build_report("x", PAYLOAD).winnable)

    @override_settings(SMOLRANK_TOP_N=2)
    def test_top_n_limit(self):
        self.assertEqual(len(build_report("x", PAYLOAD).channels), 2)

    def test_bad_payload(self):
        with self.assertRaises(APIError):
            build_report("x", {"nope": 1})

    def test_check_keyword_uses_client(self):
        client = Mock(search=Mock(return_value=PAYLOAD))
        self.assertTrue(check_keyword("x", client=client).winnable)
