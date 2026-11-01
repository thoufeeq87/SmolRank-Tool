from django.contrib import admin

from .models import SearchLog


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ("keyword", "winnable", "small_count", "total", "threshold", "created_at")
    list_filter = ("winnable", "threshold", "created_at")
    search_fields = ("keyword",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # history is an audit log: viewable and deletable, not editable
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
