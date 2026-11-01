"""Polar.sh billing settings. Values come from environment variables / .env."""
import os

POLAR_ACCESS_TOKEN = os.environ.get("POLAR_ACCESS_TOKEN", "")
POLAR_WEBHOOK_SECRET = os.environ.get("POLAR_WEBHOOK_SECRET", "")
# "sandbox" or "production". Switching to production is this one line in .env
# (plus the production access token, webhook secret and product IDs).
POLAR_SERVER = os.environ.get("POLAR_SERVER", "sandbox").strip().lower()
