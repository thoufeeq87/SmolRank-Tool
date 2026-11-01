from django.urls import path

from .views import AnalyzeView, CheckAPIView, LandingView, ResultsView

app_name = "winnability"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("analyze/", AnalyzeView.as_view(), name="analyze"),
    path("results/", ResultsView.as_view(), name="results"),
    path("api/check/", CheckAPIView.as_view(), name="api-check"),
]
