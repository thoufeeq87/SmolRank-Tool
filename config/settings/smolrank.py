"""SmolRank settings. Edit the values here (or override via environment variables)."""
import os

# A channel counts as "small" when its subscriber count is BELOW this number.
# Change it here (or set SMOLRANK_SUBSCRIBER_THRESHOLD) to tune winnability.
SMOLRANK_SUBSCRIBER_THRESHOLD = int(os.environ.get("SMOLRANK_SUBSCRIBER_THRESHOLD", 10_000))

# How many top-ranking results to inspect.
SMOLRANK_TOP_N = int(os.environ.get("SMOLRANK_TOP_N", 10))

# RapidAPI connection. The key must come from the environment, never from source control.
SMOLRANK_RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
SMOLRANK_RAPIDAPI_HOST = os.environ.get("SMOLRANK_RAPIDAPI_HOST", "smolrank.p.rapidapi.com")
SMOLRANK_API_URL = os.environ.get("SMOLRANK_API_URL", f"https://{SMOLRANK_RAPIDAPI_HOST}/search")
SMOLRANK_API_TIMEOUT = int(os.environ.get("SMOLRANK_API_TIMEOUT", 15))
