from django.urls import path

from .views import TokenPageView

app_name = "tokens"

urlpatterns = [
    path("", TokenPageView.as_view(), name="index"),
]
