"""Explicit, reauthenticated fresh-start operation. Never run on deployment."""

from django.apps import apps
from django.core import signing, serializers
from django.core.management import call_command
from django.db import transaction

from apps.accounts.models import MFADevice, Role, User
from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log
from common.constants.roles import Roles


RESET_PHRASE = "RESET CHAPELFLOW DATA"
RESET_SALT = "chapelflow-fresh-start-v2"

# Configuration survives a launch reset; assignments and personal records do not.
CONFIG_MODELS = (
    "organizations.Organization", "organizations.Branch",
    "university.University", "university.College", "university.Department",
    "accounts.Role", "accounts.Permission", "accounts.RolePermission",
    "ministries.Group",
)


def configuration_snapshot():
    records = []
    for label in CONFIG_MODELS:
        model = apps.get_model(label)
        for obj in model.objects.all():
            if label == "accounts.Role":
                obj.created_by_id = None
            elif label == "ministries.Group":
                obj.leader_id = None
            records.append(obj)
    return serializers.serialize("json", records)



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
        "preserved_configuration": list(CONFIG_MODELS),
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

        configuration = configuration_snapshot()
        admin_branch_id = locked.branch_id
        # Django's flush resets every managed table, including auth tokens,
        # audit history, CMS content, user data, and queued task results. It
        # leaves migrations and the schema in place. External Cloudinary/S3
        # objects and third-party records are outside this database.
        call_command("flush", interactive=False, verbosity=0, reset_sequences=False)
        # Keep schema/catalog configuration, but never restore deleted account
        # references, memberships, uploads, or operational records.
        for record in serializers.deserialize("json", configuration):
            record.save()
        admin_fields["branch_id"] = admin_branch_id
        admin_fields["photo_url"] = ""
        # A new UUID invalidates every pre-reset access and refresh token,
        # including another Super Admin browser session.
        restored = User.objects.create(**admin_fields)
        if device_fields:
            MFADevice.objects.create(user=restored, **device_fields)

        from scripts.seed_roles import seed_roles
        if not Role.objects.exists():
            seed_roles()
        restored.role_obj = Role.objects.filter(code=Roles.SUPER_ADMIN).first()
        restored.save(update_fields=["role_obj"])
        Branch = apps.get_model("organizations.Branch")
        if not Branch.objects.exists():
            call_command("bootstrap_chapel", verbosity=0)
        elif restored.branch_id is None:
            restored.branch = Branch.objects.filter(is_active=True).order_by("created_at").first()
            restored.save(update_fields=["branch"])
        write_audit_log(
            AuditAction.DELETE, "application.DatabaseReset", restored.pk,
            user=restored, metadata={"fresh_start": True, "previous_rows": sum(preview["counts"].values())},
        )
    return restored
