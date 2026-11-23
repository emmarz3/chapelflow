import django.db.models.deletion
import django.utils.timezone
import uuid
import apps.social.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        ("social", "0002_rename_social_comment_post_status_created_idx_social_comm_post_id_f5ef85_idx_and_more"),
        ("uploads", "0003_uploadcategory_social_post"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SocialStory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("media_type", models.CharField(choices=[("IMAGE", "Image"), ("VIDEO", "Video")], max_length=8)),
                ("caption", models.CharField(blank=True, max_length=280)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(db_index=True, default=apps.social.models.story_expiry)),
                ("author", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="upper_room_stories", to=settings.AUTH_USER_MODEL)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="upper_room_stories", to="organizations.branch")),
                ("upload", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="upper_room_stories", to="uploads.upload")),
            ],
            options={
                "db_table": "social_story",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="socialstory",
            index=models.Index(fields=["branch", "expires_at", "created_at"], name="social_story_branch_exp_idx"),
        ),
    ]
