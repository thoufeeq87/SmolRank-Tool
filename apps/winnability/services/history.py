import logging

from ..models import SearchLog

logger = logging.getLogger(__name__)


def record_search(result):
    """Store a search; never let logging break the user's request."""
    try:
        SearchLog.objects.create(
            keyword=result.keyword[:100],
            winnable=result.winnable,
            threshold=result.threshold,
            small_count=len(result.small_channels),
            total=result.total,
        )
    except Exception:
        logger.exception("Could not record search history")
