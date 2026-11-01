from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_admin_url(app_configs, **kwargs):
    if settings.ADMIN_URL == "admin/":
        return [
            Warning(
                "The admin is at the default URL /admin/.",
                hint="Set ADMIN_URL in .env to a long random string so bots can't find the login page.",
                id="core.W001",
            )
        ]
    return []
