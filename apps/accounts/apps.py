from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from django.contrib import admin

        from .views import admin_login

        # The stock admin login form needs a password; use the magic link instead.
        admin.site.login = admin_login
