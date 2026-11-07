import os

from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from common.constants.roles import Roles


class Command(BaseCommand):
    help = "Idempotently bootstrap ChapelFlow's single Super Admin from environment variables."

    def handle(self, *args, **options):
        email = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
        first_name = os.environ.get("SUPER_ADMIN_FIRST_NAME", "ChapelFlow").strip()
        last_name = os.environ.get("SUPER_ADMIN_LAST_NAME", "Administrator").strip()
        reset_password = os.environ.get("RESET_SUPER_ADMIN_PASSWORD", "").strip().lower() in {"1", "true", "yes", "on"}
        if not email or not password:
            raise CommandError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD must both be set.")

        with transaction.atomic():
            admins = list(User.objects.select_for_update().filter(role=Roles.SUPER_ADMIN))
            if len(admins) > 1:
                raise CommandError("Conflicting Super Admin accounts found; resolve the data conflict before bootstrapping.")
            if admins:
                if admins[0].email.lower() != email:
                    raise CommandError("A different Super Admin account already exists; bootstrap refused.")
                admin = admins[0]
                password_matches = check_password(password, admin.password)
                if reset_password:
                    admin.set_password(password)
                    admin.save(update_fields=["password"])
                    self.stdout.write(self.style.WARNING(
                        "RESET_SUPER_ADMIN_PASSWORD is set — Super Admin password was just reset. "
                        "Remove this env var after confirming login, or it will reset again on every deploy."
                    ))
                    return
                if not password_matches:
                    admin.set_password(password)
                    admin.save(update_fields=["password"])
                    self.stdout.write(self.style.WARNING(
                        "Super Admin password did not match SUPER_ADMIN_PASSWORD env var — "
                        "password was synced to match. If this was unintended, check your "
                        "Render environment variables."
                    ))
                    return
                self.stdout.write(self.style.SUCCESS("Super Admin already exists; no account was created."))
                return
            if User.objects.filter(email__iexact=email).exists():
                raise CommandError("The requested Super Admin email is already assigned to a non-admin account.")
            User.objects.create_superuser(
                email=email, password=password, first_name=first_name, last_name=last_name,
            )
        self.stdout.write(self.style.SUCCESS("Super Admin bootstrapped."))
