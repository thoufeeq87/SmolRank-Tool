from django.db import models


class SearchLog(models.Model):
    """One successful keyword check, recorded for review in the admin."""

    keyword = models.CharField(max_length=100, db_index=True)
    winnable = models.BooleanField()
    threshold = models.PositiveIntegerField()
    small_count = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.keyword} ({'winnable' if self.winnable else 'tough'})"
