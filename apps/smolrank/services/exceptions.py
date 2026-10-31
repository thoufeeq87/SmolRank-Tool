class SmolRankError(Exception):
    """Base error for the SmolRank service layer."""


class ConfigurationError(SmolRankError):
    """Required settings (e.g. the RapidAPI key) are missing."""


class APIError(SmolRankError):
    """The SmolRank API request failed or returned something unexpected."""
