from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, **extra):
        email = self.normalize_email(email or "").strip().lower()
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email, **extra)
        user.save(using=self._db)
        return user

    def create_user(self, email, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, **extra)

    def create_superuser(self, email, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create(email, **extra)
