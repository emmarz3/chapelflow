from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('advertising', '0002_campaign_scendey_synced_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(model_name='campaign', name='ad_category', field=models.CharField(blank=True, default='', max_length=80)),
        migrations.AddField(model_name='campaign', name='applicant_community', field=models.CharField(choices=[('STUDENT', 'Student'), ('STAFF', 'Staff')], default='STUDENT', max_length=10)),
        migrations.AddField(model_name='campaign', name='founding_offer_awarded', field=models.BooleanField(default=False)),
        migrations.AlterField(
            model_name='campaign',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending review'),
                    ('CHANGES', 'Changes requested'),
                    ('APPROVED', 'Approved, awaiting payment'),
                    ('REJECTED', 'Rejected'),
                    ('REVOKED', 'Revoked'),
                    ('ACTIVE', 'Active'),
                    ('PAUSED', 'Paused'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                max_length=12,
            ),
        ),
        migrations.AlterField(model_name='adpayment', name='campaign', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='advertising.campaign')),
        migrations.CreateModel(name='AdvertisingSettings', fields=[
            ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
            ('emergency_paused', models.BooleanField(default=False)),
            ('emergency_pause_reason', models.TextField(blank=True)),
            ('emergency_paused_at', models.DateTimeField(blank=True, null=True)),
            ('founding_offer_enabled', models.BooleanField(default=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('emergency_paused_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='advertising_pause_actions', to=settings.AUTH_USER_MODEL)),
        ], options={'verbose_name':'Advertising settings','verbose_name_plural':'Advertising settings'}),
    ]
