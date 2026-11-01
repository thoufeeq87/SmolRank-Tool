from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("tokens/", include("apps.tokens.urls")),
    path("billing/", include("apps.billing.urls")),
    path("", include("apps.winnability.urls")),
]

if settings.DEBUG:
    from apps.core import views as core_views

    urlpatterns += [
        path("__errors__/404/", core_views.preview_404),
        path("__errors__/500/", core_views.preview_500),
    ]
