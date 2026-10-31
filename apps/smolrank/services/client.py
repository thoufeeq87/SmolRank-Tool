"""Thin HTTP client for the SmolRank API on RapidAPI. Knows nothing about winnability."""
import requests
from django.conf import settings

from .exceptions import APIError, ConfigurationError


class SmolRankClient:
    def __init__(self, api_key=None, host=None, url=None, timeout=None, session=None):
        self.api_key = api_key or settings.SMOLRANK_RAPIDAPI_KEY
        self.host = host or settings.SMOLRANK_RAPIDAPI_HOST
        self.url = url or settings.SMOLRANK_API_URL
        self.timeout = timeout or settings.SMOLRANK_API_TIMEOUT
        self.session = session or requests.Session()

    def search(self, keyword):
        """Return the raw JSON payload for a keyword."""
        if not self.api_key:
            raise ConfigurationError("RAPIDAPI_KEY is not set.")
        try:
            resp = self.session.get(
                self.url,
                params={"keyword": keyword},
                headers={"x-rapidapi-key": self.api_key, "x-rapidapi-host": self.host},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise APIError(f"SmolRank API request failed: {exc}") from exc
        except ValueError as exc:
            raise APIError("SmolRank API returned invalid JSON.") from exc
