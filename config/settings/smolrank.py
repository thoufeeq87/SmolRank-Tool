"""SmolRank settings: the one place to tune the tool.

Override any value via environment variable / .env, or edit the default here.
"""
import os

# A channel counts as "winnable" if its subscribers are UNDER this number.
SMOLRANK_SUBSCRIBER_THRESHOLD = int(os.environ.get("SMOLRANK_SUBSCRIBER_THRESHOLD", 10000))

# How many top-ranked results to examine.
SMOLRANK_TOP_N = int(os.environ.get("SMOLRANK_TOP_N", 10))

# RapidAPI connection.
SMOLRANK_API_URL = os.environ.get("SMOLRANK_API_URL", "https://smolrank1.p.rapidapi.com/api/v1/check")
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST", "smolrank1.p.rapidapi.com")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
SMOLRANK_API_TIMEOUT = int(os.environ.get("SMOLRANK_API_TIMEOUT", 15))

# Cache identical keyword lookups to save API quota (0 disables).
SMOLRANK_CACHE_SECONDS = int(os.environ.get("SMOLRANK_CACHE_SECONDS", 3600))

# Dotted path of the provider client. Swap to use a different API.
SMOLRANK_CLIENT_CLASS = os.environ.get(
    "SMOLRANK_CLIENT_CLASS", "apps.winnability.clients.smolrank.SmolRankClient"
)

# Tokens charged per keyword check (refunded automatically if the check fails).
SMOLRANK_TOKEN_COST = int(os.environ.get("SMOLRANK_TOKEN_COST", 30))
