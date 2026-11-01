import os
import sys
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings.database import build_databases

from .test_security import GOOD_KEY, PG_URL, load_prod

URL = "postgresql://appuser:s3cret@viaduct.proxy.rlwy.net:5432/railway"


class BuildDatabasesTests(SimpleTestCase):
    def test_no_url_uses_sqlite(self):
        db = build_databases(env={}, argv=["manage.py", "runserver"])["default"]
        self.assertTrue(db["ENGINE"].endswith("sqlite3"))
        self.assertEqual(db["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def test_url_selects_postgres_with_connection_reuse(self):
        db = build_databases(env={"DATABASE_URL": URL}, argv=["manage.py", "runserver"])["default"]
        self.assertTrue(db["ENGINE"].endswith("postgresql"))
        self.assertEqual((db["HOST"], db["PORT"], db["NAME"], db["USER"]), ("viaduct.proxy.rlwy.net", 5432, "railway", "appuser"))
        self.assertEqual(db["CONN_MAX_AGE"], 600)
        self.assertTrue(db["CONN_HEALTH_CHECKS"])
        self.assertNotIn("transaction_mode", db.get("OPTIONS", {}))  # SQLite-only option must not leak

    def test_ssl_can_be_required(self):
        env = {"DATABASE_URL": URL, "DATABASE_SSL_REQUIRE": "True"}
        db = build_databases(env=env, argv=["manage.py", "runserver"])["default"]
        self.assertEqual(db["OPTIONS"]["sslmode"], "require")

    def test_manage_test_stays_on_sqlite_even_with_a_url(self):
        db = build_databases(env={"DATABASE_URL": URL}, argv=["manage.py", "test"])["default"]
        self.assertTrue(db["ENGINE"].endswith("sqlite3"))

    def test_test_on_postgres_flag_opts_in(self):
        env = {"DATABASE_URL": URL, "TEST_ON_POSTGRES": "1"}
        db = build_databases(env=env, argv=["manage.py", "test"])["default"]
        self.assertTrue(db["ENGINE"].endswith("postgresql"))

    def test_production_refuses_sqlite_fallback(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "DATABASE_URL is required in production"):
            build_databases(env={}, argv=["manage.py", "runserver"], require_url=True)

    def test_production_always_uses_the_url_even_while_testing(self):
        db = build_databases(env={"DATABASE_URL": URL}, argv=["manage.py", "test"], require_url=True)["default"]
        self.assertTrue(db["ENGINE"].endswith("postgresql"))


class ProdDatabaseTests(SimpleTestCase):
    def test_prod_settings_use_postgres_from_database_url(self):
        prod = load_prod({"DJANGO_SECRET_KEY": GOOD_KEY, "DATABASE_URL": PG_URL})
        self.assertTrue(prod.DATABASES["default"]["ENGINE"].endswith("postgresql"))
        self.assertEqual(prod.DATABASES["default"]["HOST"], "db.example.com")

    def test_prod_refuses_to_start_without_database_url(self):
        import importlib

        sys.modules.pop("config.settings.prod", None)
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": GOOD_KEY}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            try:
                with self.assertRaisesMessage(ImproperlyConfigured, "DATABASE_URL"):
                    importlib.import_module("config.settings.prod")
            finally:
                sys.modules.pop("config.settings.prod", None)
