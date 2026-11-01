class BaseProviderClient:
    """Interface for a keyword-data provider.

    Implement `check(keyword)` returning a dict shaped like the SmolRank
    response ({"keyword", "results": [...], "suggestions", ...}) and point
    SMOLRANK_CLIENT_CLASS at it to swap providers.
    """

    def check(self, keyword):
        raise NotImplementedError
