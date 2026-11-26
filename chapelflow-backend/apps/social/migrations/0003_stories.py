from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("social", "0002_rename_social_comment_post_status_created_idx_social_comm_post_id_f5ef85_idx_and_more")]
    operations = [
        migrations.AddField(model_name="socialpost", name="is_story", field=models.BooleanField(default=False, db_index=True)),
        migrations.AddField(model_name="socialpost", name="expires_at", field=models.DateTimeField(null=True, blank=True)),
    ]
