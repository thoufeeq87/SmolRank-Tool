from django.urls import path

from . import views

app_name = "smolrank"
urlpatterns = [path("", views.index, name="index")]
