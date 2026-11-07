from django.db import migrations


PROTOCOL_NAMES = {"chapel protocol", "chapel protocol unit", "protocol unit"}


def create_chapel_protocol_units(apps, schema_editor):
    Branch = apps.get_model("organizations", "Branch")
    Group = apps.get_model("ministries", "Group")
    for branch in Branch.objects.filter(branch_type="CHAPEL", is_active=True):
        existing = Group.objects.filter(branch=branch, group_type="UNIT")
        if any(group.name.strip().casefold() in PROTOCOL_NAMES for group in existing):
            continue
        Group.objects.create(
            branch=branch,
            name="Chapel Protocol",
            group_type="UNIT",
            description="Custody and preparation team for ChapelFlow inventory.",
            is_active=True,
        )


def remove_seeded_chapel_protocol_units(apps, schema_editor):
    Group = apps.get_model("ministries", "Group")
    Group.objects.filter(
        name="Chapel Protocol",
        group_type="UNIT",
        description="Custody and preparation team for ChapelFlow inventory.",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0003_assetmaintenance_assetmovement_asset_asset_tag_and_more"),
        ("ministries", "0001_initial"),
    ]

    operations = [migrations.RunPython(create_chapel_protocol_units, remove_seeded_chapel_protocol_units)]
