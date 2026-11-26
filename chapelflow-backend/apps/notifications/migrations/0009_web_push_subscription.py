import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("notifications", "0008_alter_notification_category"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="WebPushSubscription", fields=[
        ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
        ("endpoint", models.URLField(max_length=2048, unique=True)),
        ("p256dh", models.CharField(max_length=256)),
        ("auth", models.CharField(max_length=256)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name="web_push_subscriptions", on_delete=django.db.models.deletion.CASCADE)),
    ], options={"db_table": "notifications_web_push_subscription"})]
