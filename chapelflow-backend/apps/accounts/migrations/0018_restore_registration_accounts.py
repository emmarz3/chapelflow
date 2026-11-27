"""Restore members stranded by the temporary email verification requirement.

Only the registration cohort is eligible. Inactive institutional accounts,
deleted accounts, people who have logged in before, and inactive memberships
remain untouched.
"""

from datetime import datetime, timezone

from django.db import migrations


START = datetime(2026, 11, 26, 2, 12, tzinfo=timezone.utc)
END = datetime(2026, 11, 27, 8, 35, tzinfo=timezone.utc)


def restore_stranded_registrations(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Member = apps.get_model("members", "Member")
    AuditLog = apps.get_model("audit", "AuditLog")
    database = schema_editor.connection.alias

    registered_ids = AuditLog.objects.using(database).filter(
        action="MEMBER_SELF_REGISTER", resource_type="member",
        created_at__gte=START, created_at__lte=END,
    ).values_list("user_id", flat=True)
    active_member_ids = Member.objects.using(database).filter(
        membership_status="ACTIVE",
    ).values_list("user_id", flat=True)
    stranded = User.objects.using(database).filter(
        role="MEMBER", is_active=False, deleted_at__isnull=True,
        last_login__isnull=True, date_joined__gte=START, date_joined__lte=END,
        pk__in=registered_ids, member_profile__user_id__in=active_member_ids,
    )
    restored = 0
    for account in stranded.iterator():
        if AuditLog.objects.using(database).filter(
            resource_type="accounts.User", resource_id=str(account.pk),
            action__in=("UPDATE", "DELETE", "ROLE_CHANGE"),
        ).exists():
            continue
        updated = User.objects.using(database).filter(
            pk=account.pk, is_active=False, deleted_at__isnull=True,
        ).update(is_active=True)
        if updated:
            AuditLog.objects.using(database).create(
                action="UPDATE", resource_type="accounts.User", resource_id=str(account.pk),
                metadata={"reason": "restore_registration_without_email_verification"},
            )
            restored += 1
    print(f"Restored {restored} inactive self-registered member accounts from the email-verification cohort.")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0017_user_bio"),
        ("members", "0001_initial"),
        ("audit", "0001_initial"),
    ]
    operations = [migrations.RunPython(restore_stranded_registrations, migrations.RunPython.noop)]
