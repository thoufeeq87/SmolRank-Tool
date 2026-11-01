from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create (or promote) a staff superuser by email. There are no passwords: sign in via magic link."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).strip().lower()
        if "@" not in email:
            raise CommandError("Enter a valid email address.")
        user, created = User.objects.get_or_create(email=email)
        user.is_staff = user.is_superuser = True
        user.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Promoted'} admin {email}"))
