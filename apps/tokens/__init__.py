"""Token system. Import the public API from here:

    from apps.tokens import add_tokens, consume_tokens, get_balance, get_transactions

Exports are lazy so importing this package never touches models before the
Django app registry is ready.
"""

__all__ = [
    "add_tokens",
    "consume_tokens",
    "get_balance",
    "get_transactions",
    "TokenError",
    "InvalidAmount",
    "InsufficientTokens",
]

_EXCEPTIONS = {"TokenError", "InvalidAmount", "InsufficientTokens"}


def __getattr__(name):
    if name in _EXCEPTIONS:
        from . import exceptions

        return getattr(exceptions, name)
    if name in __all__:
        from . import api

        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
