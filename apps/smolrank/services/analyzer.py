"""Winnability logic: pure functions, no I/O, easy to test."""
from dataclasses import dataclass, field

from django.conf import settings

from .client import SmolRankClient
from .exceptions import APIError

# Field names in the SmolRank API response.
RESULT_LIST_KEY = "results"


@dataclass
class ChannelResult:
    rank: int
    channel: str
    subscribers: int | None
    is_small: bool
    video_title: str = ""
    published_date: str = ""
    is_outdated: bool = False
    view_count: int | None = None
    reach_multiplier: float | None = None
    is_outlier: bool = False


@dataclass
class WinnabilityReport:
    keyword: str
    threshold: int
    channels: list[ChannelResult] = field(default_factory=list)
    freshness_opportunity: bool = False
    suggestions: list = field(default_factory=list)

    @property
    def small_channels(self):
        return [c for c in self.channels if c.is_small]

    @property
    def winnable(self):
        return bool(self.small_channels)


def _to_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_results(payload):
    results = payload.get(RESULT_LIST_KEY) if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise APIError("Unexpected SmolRank API response shape.")
    return results


def build_report(keyword, payload, threshold=None, top_n=None):
    """Build a report. Winnability uses OUR threshold setting, not the API's."""
    threshold = settings.SMOLRANK_SUBSCRIBER_THRESHOLD if threshold is None else threshold
    top_n = settings.SMOLRANK_TOP_N if top_n is None else top_n
    report = WinnabilityReport(
        keyword=keyword,
        threshold=threshold,
        freshness_opportunity=bool(payload.get("freshness_opportunity")),
        suggestions=payload.get("suggestions") or [],
    )
    for position, item in enumerate(extract_results(payload)[:top_n], start=1):
        subs = _to_int(item.get("subscriber_count"))
        report.channels.append(
            ChannelResult(
                rank=item.get("rank") or position,
                channel=str(item.get("channel_title") or "Unknown"),
                subscribers=subs,
                is_small=subs is not None and subs < threshold,
                video_title=item.get("video_title") or "",
                published_date=item.get("published_date") or "",
                is_outdated=bool(item.get("is_outdated")),
                view_count=_to_int(item.get("view_count")),
                reach_multiplier=item.get("reach_multiplier"),
                is_outlier=bool(item.get("is_outlier")),
            )
        )
    return report


def check_keyword(keyword, client=None):
    client = client or SmolRankClient()
    return build_report(keyword, client.search(keyword))
