"""Winnability logic: pure functions, no I/O, easy to test."""
from dataclasses import dataclass, field

from django.conf import settings

from .client import SmolRankClient
from .exceptions import APIError

# Keys the API payload might use; adjust here once the real response shape is confirmed.
RESULT_LIST_KEYS = ("results", "videos", "items", "data")
CHANNEL_NAME_KEYS = ("channel_name", "channelTitle", "channel", "author")
SUBSCRIBER_KEYS = ("subscribers", "subscriber_count", "subscriberCount", "channel_subscribers")


@dataclass
class ChannelResult:
    rank: int
    channel: str
    subscribers: int | None
    is_small: bool


@dataclass
class WinnabilityReport:
    keyword: str
    threshold: int
    channels: list[ChannelResult] = field(default_factory=list)

    @property
    def small_channels(self):
        return [c for c in self.channels if c.is_small]

    @property
    def winnable(self):
        return bool(self.small_channels)


def _first(item, keys, default=None):
    for key in keys:
        if item.get(key) is not None:
            return item[key]
    return default


def _to_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_results(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in RESULT_LIST_KEYS:
            if isinstance(payload.get(key), list):
                return payload[key]
    raise APIError("Unexpected SmolRank API response shape.")


def build_report(keyword, payload, threshold=None, top_n=None):
    threshold = settings.SMOLRANK_SUBSCRIBER_THRESHOLD if threshold is None else threshold
    top_n = settings.SMOLRANK_TOP_N if top_n is None else top_n
    report = WinnabilityReport(keyword=keyword, threshold=threshold)
    for rank, item in enumerate(extract_results(payload)[:top_n], start=1):
        subs = _to_int(_first(item, SUBSCRIBER_KEYS))
        report.channels.append(
            ChannelResult(
                rank=rank,
                channel=str(_first(item, CHANNEL_NAME_KEYS, "Unknown")),
                subscribers=subs,
                is_small=subs is not None and subs < threshold,
            )
        )
    return report


def check_keyword(keyword, client=None):
    client = client or SmolRankClient()
    return build_report(keyword, client.search(keyword))
