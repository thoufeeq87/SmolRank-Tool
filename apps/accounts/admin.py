from django.contrib import admin

from .models import MagicLink, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "is_staff", "is_superuser", "date_joined", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email",)
    ordering = ("-date_joined",)
    readonly_fields = ("last_login", "date_joined")
    fields = (
        "email", "is_active", "is_staff", "is_superuser",
        "groups", "user_permissions", "last_login", "date_joined",
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used_at")
    list_filter = ("created_at",)
    search_fields = ("user__email",)
    readonly_fields = ("user", "token_hash", "created_at", "expires_at", "used_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
