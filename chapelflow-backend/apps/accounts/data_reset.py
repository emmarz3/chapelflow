"""Explicit, reauthenticated fresh-start operation. Never run on deployment."""

from django.apps import apps
from django.core import signing
from django.core.management import call_command
from django.db import transaction

from apps.accounts.models import MFADevice, Role, User
from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log
from common.constants.roles import Roles


RESET_PHRASE = "RESET CHAPELFLOW DATA"
RESET_SALT = "chapelflow-fresh-start-v1"


def reset_preview(admin):
    # Show the actual blast radius, including Django auth and Celery rows.
    counts = {
        model._meta.label: model._base_manager.count()
        for model in apps.get_models(include_auto_created=False)
        if model._meta.managed and model._meta.db_table
    }
    return {
        "accounts_to_remove": User.objects.exclude(pk=admin.pk).count(),
        "database_rows": sum(counts.values()),
        "counts": counts,
        "confirmation": RESET_PHRASE,
        "token": signing.dumps({"admin": str(admin.pk), "counts": counts}, salt=RESET_SALT),
    }


def reset_database(admin, token):
    preview = signing.loads(token, salt=RESET_SALT, max_age=300)
    if preview.get("admin") != str(admin.pk) or preview.get("counts") != reset_preview(admin)["counts"]:
        raise ValueError("The data changed since the preview. Review the counts again.")

    with transaction.atomic():
        # Serialize only this administrator's identity and authenticator; the
        # original password hash remains valid and no secret is returned.
        locked = User.objects.select_for_update().get(pk=admin.pk, role=Roles.SUPER_ADMIN)
        admin_fields = {
            field.attname: getattr(locked, field.attname)
            for field in User._meta.concrete_fields
            if field.attname not in {"id", "role_obj_id", "branch_id", "institutional_group_id", "created_by_id"}
        }
        device = MFADevice.objects.filter(user=locked).first()
        device_fields = ({"secret": device.secret, "confirmed": device.confirmed} if device else None)

        # Django's flush resets every managed table, including auth tokens,
        # audit history, CMS content, user data, and queued task results. It
        # leaves migrations and the schema in place. External Cloudinary/S3
        # objects and third-party records are outside this database.
        call_command("flush", interactive=False, verbosity=0)
        # A new UUID invalidates every pre-reset access and refresh token,
        # including another Super Admin browser session.
        restored = User.objects.create(**admin_fields)
        if device_fields:
            MFADevice.objects.create(user=restored, **device_fields)

        from scripts.seed_roles import seed_roles
        seed_roles()
        restored.role_obj = Role.objects.filter(code=Roles.SUPER_ADMIN).first()
        restored.save(update_fields=["role_obj"])
        call_command("bootstrap_chapel", verbosity=0)
        write_audit_log(
            AuditAction.DELETE, "application.DatabaseReset", restored.pk,
            user=restored, metadata={"fresh_start": True, "previous_rows": sum(preview["counts"].values())},
        )
    return restored
