import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_subscription_programs(apps, schema_editor):
    Program = apps.get_model("advertising", "AdSubscriptionProgram")
    Campaign = apps.get_model("advertising", "Campaign")

    defaults = [
        {
            "code": "campus-brand",
            "name": "Campus Brand",
            "description": "Rotating sponsored placement on the ChapelFlow homepage and events page.",
            "monthly_price_ngn": 3000,
            "base_plan": "CAMPUS",
            "placements": ["home", "events"],
            "sort_order": 10,
        },
        {
            "code": "featured-brand",
            "name": "Featured Brand",
            "description": "Higher rotation priority on the ChapelFlow homepage and events page.",
            "monthly_price_ngn": 7500,
            "base_plan": "FEATURED",
            "placements": ["home", "events"],
            "sort_order": 20,
        },
    ]
    for values in defaults:
        program, _ = Program.objects.get_or_create(
            code=values["code"],
            defaults=values,
        )
        amount_kobo = values["monthly_price_ngn"] * 100
        Campaign.objects.filter(plan=values["base_plan"]).update(
            program=program,
            monthly_price_kobo=amount_kobo,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("advertising", "0003_founding_offer_advertising_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdSubscriptionProgram",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("code", models.SlugField(max_length=48, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("monthly_price_ngn", models.PositiveIntegerField()),
                ("base_plan", models.CharField(
                    choices=[("CAMPUS", "Campus Brand"), ("FEATURED", "Featured Brand")],
                    default="CAMPUS", max_length=12,
                )),
                ("placements", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_ad_programs", to=settings.AUTH_USER_MODEL,
                )),
                ("updated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="updated_ad_programs", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.AddIndex(
            model_name="adsubscriptionprogram",
            index=models.Index(fields=["is_active", "sort_order"], name="advertising_is_acti_2bcff2_idx"),
        ),
        migrations.AddField(
            model_name="campaign",
            name="program",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="campaigns", to="advertising.adsubscriptionprogram",
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="monthly_price_kobo",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="campaign",
            name="submission_revision",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="paystackplan",
            name="plan",
            field=models.CharField(
                blank=True, null=True,
                choices=[("CAMPUS", "Campus Brand"), ("FEATURED", "Featured Brand")],
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="paystackplan",
            name="program",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="paystack_plans", to="advertising.adsubscriptionprogram",
            ),
        ),
        migrations.RunPython(seed_subscription_programs, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="paystackplan",
            constraint=models.UniqueConstraint(
                fields=("plan",),
                condition=models.Q(program__isnull=True, plan__isnull=False),
                name="ad_paystack_legacy_plan_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="paystackplan",
            constraint=models.UniqueConstraint(
                fields=("program", "amount_kobo"),
                condition=models.Q(program__isnull=False),
                name="ad_paystack_program_amount_unique",
            ),
        ),
    ]
