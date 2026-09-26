from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="upload",
            name="category",
            field=models.CharField(
                choices=[
                    ("MEMBER_PHOTO", "Member Photo"),
                    ("BRANCH_LOGO", "Branch Logo"),
                    ("EVENT_IMAGE", "Event Image"),
                    ("DOCUMENT", "Document"),
                    ("SERMON_AUDIO", "Sermon Audio"),
                    ("MEDIA_CONTENT", "Published media content"),
                    ("OTHER", "Other"),
                ],
                default="OTHER",
                max_length=20,
            ),
        ),
    ]
