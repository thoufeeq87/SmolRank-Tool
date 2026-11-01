from django.urls import path

from .views import CancelView, CheckoutView, PackagesView, SuccessView, polar_webhook

app_name = "billing"

urlpatterns = [
    path("", PackagesView.as_view(), name="packages"),
    path("checkout/<int:package_id>/", CheckoutView.as_view(), name="checkout"),
    path("success/", SuccessView.as_view(), name="success"),
    path("cancel/", CancelView.as_view(), name="cancel"),
    path("webhook/", polar_webhook, name="webhook"),
]
