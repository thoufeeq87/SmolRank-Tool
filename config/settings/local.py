"""Development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = SECRET_KEY or "dev-insecure-key-change-me"  # noqa: F405
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
