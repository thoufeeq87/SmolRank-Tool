import hashlib

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

from ..exceptions import SmolRankAPIError, SmolRankResponseError
from ..schemas import ChannelResult, WinnabilityResult


def _parse_row(row, threshold):
    try:
        subs = int(row["subscriber_count"])
        return ChannelResult(
            rank=int(row["rank"]),
            video_title=str(row.get("video_title", "")),
            channel_title=str(row.get("channel_title", "")),
            subscriber_count=subs,
            view_count=int(row.get("view_count") or 0),
            published_date=str(row.get("published_date") or ""),
            reach_multiplier=float(row.get("reach_multiplier") or 0),
            is_outlier=bool(row.get("is_outlier")),
            is_outdated=bool(row.get("is_outdated")),
            is_small=subs < threshold,  # API's is_small is ignored
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise SmolRankResponseError("SmolRank API returned an unexpected response.") from exc


def analyze_payload(payload, threshold, top_n):
    """Decide winnability locally from subscriber_count and our own threshold."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SmolRankResponseError("SmolRank API returned an unexpected response.")
    rows = [_parse_row(r, threshold) for r in payload["results"]]
    results = sorted(rows, key=lambda c: c.rank)[:top_n]
    small = [c for c in results if c.is_small]
    suggestions = payload.get("suggestions") or []
    return WinnabilityResult(
        keyword=str(payload.get("keyword", "")),
        threshold=threshold,
        winnable=bool(small),
        results=results,
        small_channels=small,
        freshness_opportunity=bool(payload.get("freshness_opportunity")),
        suggestions=[str(s) for s in suggestions] if isinstance(suggestions, list) else [],
    )


def get_client():
    return import_string(settings.SMOLRANK_CLIENT_CLASS)()


def check_keyword(keyword, client=None):
    keyword = keyword.strip()
    if not keyword:
        raise SmolRankAPIError("Keyword is required.")
    # hashed: raw keywords contain spaces/punctuation that are invalid cache-key characters
    cache_key = "smolrank:" + hashlib.sha256(keyword.lower().encode()).hexdigest()
    payload = cache.get(cache_key)
    if payload is None:
        payload = (client or get_client()).check(keyword)
        # validate before caching so bad payloads are never stored
        result = analyze_payload(payload, settings.SMOLRANK_SUBSCRIBER_THRESHOLD, settings.SMOLRANK_TOP_N)
        if settings.SMOLRANK_CACHE_SECONDS:
            cache.set(cache_key, payload, settings.SMOLRANK_CACHE_SECONDS)
        return result
    return analyze_payload(payload, settings.SMOLRANK_SUBSCRIBER_THRESHOLD, settings.SMOLRANK_TOP_N)
