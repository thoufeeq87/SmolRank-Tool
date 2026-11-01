from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Email-only user. There is no password: sign-in is via magic link."""

    password = None  # drop AbstractBaseUser's password column

    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class MagicLink(models.Model):
    """A one-time sign-in token. Only the SHA-256 of the token is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="magic_links")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"MagicLink for {self.user.email} ({self.created_at:%Y-%m-%d %H:%M})"
