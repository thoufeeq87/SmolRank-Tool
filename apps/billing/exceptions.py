class BillingError(Exception):
    """Base billing error. Messages are safe to show to users."""


class BillingConfigError(BillingError):
    """Polar settings are missing or invalid."""


class CheckoutError(BillingError):
    """A checkout session could not be created."""
