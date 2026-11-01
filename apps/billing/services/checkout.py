import logging

from django.conf import settings
from django.urls import reverse

from ..exceptions import BillingConfigError, CheckoutError
from .polar_client import get_client

logger = logging.getLogger(__name__)


def create_checkout_url(user, package):
    """Create a Polar hosted checkout session and return its URL.

    The user and package IDs are passed as external customer ID and metadata so the
    order.paid webhook knows who to credit. Nothing is credited here.
    """
    try:
        client = get_client()
    except BillingConfigError:
        logger.exception("Polar is not configured")
        raise CheckoutError("Payments are not available right now. Please try again later.")

    try:
        checkout = client.checkouts.create(
            products=[package.polar_product_id],
            external_customer_id=str(user.pk),
            metadata={"user_id": str(user.pk), "package_id": str(package.pk)},
            customer_email=user.email,
            success_url=settings.SITE_URL + reverse("billing:success") + "?checkout_id={CHECKOUT_ID}",
            return_url=settings.SITE_URL + reverse("billing:cancel"),
        )
    except Exception as exc:
        logger.exception("Polar checkout creation failed for user=%s package=%s", user.pk, package.pk)
        raise CheckoutError("We couldn't start the checkout. Please try again in a moment.") from exc

    if not getattr(checkout, "url", None):
        logger.error("Polar checkout response had no url (user=%s package=%s)", user.pk, package.pk)
        raise CheckoutError("We couldn't start the checkout. Please try again in a moment.")
    logger.info("Created checkout %s for user=%s package=%s", checkout.id, user.pk, package.pk)
    return checkout.url
