from django.contrib import admin

from .models import Order, TokenPackage


@admin.register(TokenPackage)
class TokenPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "token_amount", "price", "polar_product_id", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "polar_product_id")
    ordering = ("sort_order", "id")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("polar_order_id", "user", "package", "tokens", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("polar_order_id", "user__email")
    date_hierarchy = "created_at"

    # orders are a record of what Polar told us: view only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
