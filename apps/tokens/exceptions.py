class TokenError(Exception):
    """Base class for token errors."""


class InvalidAmount(TokenError, ValueError):
    """Amount must be a positive integer."""


class InsufficientTokens(TokenError):
    def __init__(self, balance, required):
        self.balance = balance
        self.required = required
        super().__init__(f"Insufficient tokens: balance {balance}, required {required}.")
