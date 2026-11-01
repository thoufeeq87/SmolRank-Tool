class SmolRankAPIError(Exception):
    """Base error for any SmolRank API failure; message is safe to show users."""


class SmolRankAuthError(SmolRankAPIError):
    pass


class SmolRankRateLimitError(SmolRankAPIError):
    pass


class SmolRankTimeoutError(SmolRankAPIError):
    pass


class SmolRankResponseError(SmolRankAPIError):
    """The API answered, but the payload was not the expected shape."""
