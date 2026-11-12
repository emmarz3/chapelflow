from django.db import migrations


def backfill_categories(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    for notification in Notification.objects.filter(href="").iterator(chunk_size=500):
        if notification.source_prayer_request_id:
            category, href = "PUBLIC_PRAYER", "/app/care"
        elif notification.source_announcement_id:
            category, href = "ANNOUNCEMENT", "/app/announcements"
        elif notification.birthday_announcement_id:
            category, href = "BIRTHDAY", "/app"
        else:
            category, href = "OTHER", "/app/notifications"
        Notification.objects.filter(pk=notification.pk).update(category=category, href=href)


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_notification_attempts_notification_category_and_more")]
    operations = [migrations.RunPython(backfill_categories, migrations.RunPython.noop)]
