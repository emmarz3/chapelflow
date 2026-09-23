from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create the default Chrisland University Chapel and its protocol unit."

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import User
        from apps.ministries.models import Group
        from apps.organizations.models import Branch, Organization

        organization, _ = Organization.objects.get_or_create(
            slug="chrisland", defaults={"name": "Chrisland University"}
        )
        branch, _ = Branch.objects.get_or_create(
            organization=organization,
            name="Chrisland University Chapel",
            defaults={
                "branch_type": Branch.BranchType.CHAPEL,
                "city": "Abeokuta",
                "country": "Nigeria",
            },
        )
        Group.objects.get_or_create(
            branch=branch,
            name="Chapel Protocol",
            group_type="UNIT",
            defaults={
                "is_active": True,
                "description": "Custody and preparation team for ChapelFlow inventory.",
            },
        )
        User.objects.filter(role="SUPER_ADMIN", branch__isnull=True).update(branch=branch)
        self.stdout.write(self.style.SUCCESS("Chrisland University Chapel is ready."))
