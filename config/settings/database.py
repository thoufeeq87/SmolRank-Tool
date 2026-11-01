"""Database settings.

DATABASE_URL set      -> PostgreSQL (e.g. Railway). Local dev uses Railway's *public* URL; an app
                         deployed on Railway uses the reference variable ${{Postgres.DATABASE_URL}}.
DATABASE_URL not set  -> a local SQLite file (offline development).
`manage.py test` under the dev settings always uses SQLite (fast, and never creates a test database on a
remote server) unless TEST_ON_POSTGRES=1, which is how the concurrency tests are proven against real Postgres.
"""
import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

_BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _flag(env, name, default=False):
    return env.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def sqlite_config():
    return {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _BASE_DIR / "db.sqlite3",
        # IMMEDIATE: concurrent writers wait for the lock instead of failing mid-transaction
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
        # file-based test DB so multi-threaded tests share it reliably
        "TEST": {"NAME": _BASE_DIR / "test_db.sqlite3"},
    }


def build_databases(env=None, argv=None, require_url=False):
    """Return the DATABASES setting. `require_url=True` (production) forbids the SQLite fallback."""
    env = os.environ if env is None else env
    argv = sys.argv if argv is None else argv
    url = env.get("DATABASE_URL", "").strip()

    if require_url and not url:
        raise ImproperlyConfigured(
            "DATABASE_URL is required in production (Railway's disk is wiped on deploy, so SQLite would lose data)."
        )

    testing = argv[1:2] == ["test"]
    if not url or (testing and not require_url and not _flag(env, "TEST_ON_POSTGRES")):
        return {"default": sqlite_config()}

    return {
        "default": dj_database_url.parse(
            url,
            conn_max_age=600,  # reuse connections between requests
            conn_health_checks=True,  # drop a connection that Railway/Postgres closed meanwhile
            ssl_require=_flag(env, "DATABASE_SSL_REQUIRE"),
        )
    }


DATABASES = build_databases()
