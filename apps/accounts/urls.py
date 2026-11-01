from django.urls import path

from .views import LinkSentView, LoginView, LogoutView, VerifyView

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("sent/", LinkSentView.as_view(), name="sent"),
    path("verify/<str:token>/", VerifyView.as_view(), name="verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
