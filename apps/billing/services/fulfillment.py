"""Turn a verified Polar order.paid event into tokens, exactly once."""
import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.tokens import add_tokens
from apps.tokens.models import TokenAccount

from ..models import Order, TokenPackage

logger = logging.getLogger("apps.billing.webhooks")

CREDITED, DUPLICATE, IGNORED = "credited", "duplicate", "ignored"


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_user(order):
    """Buyer from our metadata, cross-checked against the Polar customer's external ID."""
    metadata = getattr(order, "metadata", None) or {}
    customer = getattr(order, "customer", None)
    from_meta = _to_int(metadata.get("user_id"))
    from_customer = _to_int(getattr(customer, "external_id", None))
    if from_meta and from_customer and from_meta != from_customer:
        logger.error("Order %s: metadata user_id=%s != customer external_id=%s", order.id, from_meta, from_customer)
        return None
    user_id = from_meta or from_customer
    if not user_id:
        logger.error("Order %s: no user_id in metadata or customer external_id", order.id)
        return None
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        logger.error("Order %s: user %s does not exist", order.id, user_id)
    return user


def _resolve_package(order):
    metadata = getattr(order, "metadata", None) or {}
    package_id = _to_int(metadata.get("package_id"))
    package = TokenPackage.objects.filter(pk=package_id).first() if package_id else None
    if package is None and getattr(order, "product_id", None):
        package = TokenPackage.objects.filter(polar_product_id=order.product_id).first()
    if package is None:
        logger.error("Order %s: no matching package (metadata=%s product=%s)", order.id, metadata, order.product_id)
        return None
    if package.polar_product_id != order.product_id:
        logger.error(
            "Order %s: product %s does not match package %s product %s; not crediting",
            order.id, order.product_id, package.pk, package.polar_product_id,
        )
        return None
    return package


def fulfill_paid_order(order):
    """Credit tokens for a paid Polar order. Returns "credited", "duplicate" or "ignored".

    Safe to call repeatedly for the same order (Polar redelivers events): the unique
    Order.polar_order_id decides, inside one transaction that also holds the user's
    token-balance row lock.
    """
    if getattr(order, "status", None) != "paid":
        logger.info("Order %s ignored: status=%s", order.id, getattr(order, "status", None))
        return IGNORED

    user = _resolve_user(order)
    package = _resolve_package(order) if user else None
    if user is None or package is None:
        return IGNORED  # logged above; 200 because a retry cannot fix it

    with transaction.atomic():
        TokenAccount.objects.get_or_create(user=user)
        TokenAccount.objects.select_for_update().get(user=user)  # serialise per-user credits
        try:
            with transaction.atomic():
                Order.objects.create(
                    user=user,
                    package=package,
                    tokens=package.token_amount,
                    polar_order_id=order.id,
                    status=order.status,
                )
        except IntegrityError:
            if Order.objects.filter(polar_order_id=order.id).exists():
                logger.info("Order %s already processed; skipping", order.id)
                return DUPLICATE
            raise
        add_tokens(
            user,
            package.token_amount,
            reason=f"Token purchase: {package.name}",
            reference=f"polar:{order.id}",
            idempotency_key=f"polar-order-{order.id}",
        )
    logger.info("Order %s credited %s tokens to user %s", order.id, package.token_amount, user.pk)
    return CREDITED
