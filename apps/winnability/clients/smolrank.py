import requests
from django.conf import settings

from .base import BaseProviderClient
from ..exceptions import (
    SmolRankAPIError,
    SmolRankAuthError,
    SmolRankRateLimitError,
    SmolRankTimeoutError,
)


class SmolRankClient(BaseProviderClient):
    """Thin HTTP wrapper around the SmolRank RapidAPI. No business logic."""

    def __init__(self, url=None, host=None, key=None, timeout=None):
        self.url = url or settings.SMOLRANK_API_URL
        self.host = host or settings.RAPIDAPI_HOST
        self.key = key or settings.RAPIDAPI_KEY
        self.timeout = timeout or settings.SMOLRANK_API_TIMEOUT

    @staticmethod
    def _limit_message(resp):
        """Prefer the API's own explanation (e.g. its daily fresh-lookup cap) over a generic one."""
        try:
            detail = resp.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:300]
        return "SmolRank API rate limit reached."

    def check(self, keyword):
        if not self.key:
            raise SmolRankAuthError("RAPIDAPI_KEY is not configured.")
        headers = {"x-rapidapi-key": self.key, "x-rapidapi-host": self.host}
        try:
            resp = requests.get(
                self.url, headers=headers, params={"keyword": keyword}, timeout=self.timeout
            )
        except requests.Timeout as exc:
            raise SmolRankTimeoutError("The SmolRank API timed out. Try again.") from exc
        except requests.RequestException as exc:
            raise SmolRankAPIError("Could not reach the SmolRank API.") from exc

        if resp.status_code in (401, 403):
            raise SmolRankAuthError("SmolRank API rejected the API key.")
        if resp.status_code == 429:
            raise SmolRankRateLimitError(self._limit_message(resp))
        if resp.status_code != 200:
            raise SmolRankAPIError(f"SmolRank API error (HTTP {resp.status_code}).")
        try:
            return resp.json()
        except ValueError as exc:
            raise SmolRankAPIError("SmolRank API returned invalid JSON.") from exc
