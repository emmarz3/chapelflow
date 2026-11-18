from django.db import migrations


def backfill_users(apps, schema_editor):
    Preference = apps.get_model("communications", "CommunicationPreference")
    for preference in Preference.objects.filter(user__isnull=True, member__user__isnull=False).select_related("member").iterator():
        Preference.objects.filter(pk=preference.pk).update(user_id=preference.member.user_id)


class Migration(migrations.Migration):
    dependencies = [("communications", "0005_communicationpreference_admin_alerts_enabled_and_more")]
    operations = [migrations.RunPython(backfill_users, migrations.RunPython.noop)]
