from django.db import migrations, models


def set_audience_prices(apps, schema_editor):
    Program = apps.get_model('advertising', 'AdSubscriptionProgram')
    Settings = apps.get_model('advertising', 'AdvertisingSettings')
    Program.objects.filter(code='campus-brand').update(
        name='School Student Ads', description='Monthly sponsored placement for Chrisland University students on the homepage and events page.',
        monthly_price_ngn=3500, audience='STUDENT',
    )
    Program.objects.filter(code='featured-brand').update(
        name='Outside Brand Ads', description='Monthly sponsored placement for advertisers outside the student community on the homepage and events page.',
        monthly_price_ngn=5000, audience='OUTSIDER',
    )
    # Previously awarded first-month discounts remain valid; new applicants see the stated rates.
    Settings.objects.update(founding_offer_enabled=False)


class Migration(migrations.Migration):
    dependencies = [('advertising', '0004_subscription_program_catalogue')]
    operations = [
        migrations.AddField(
            model_name='adsubscriptionprogram', name='audience',
            field=models.CharField(max_length=10, choices=[('STUDENT', 'School students'), ('OUTSIDER', 'Outside advertisers')], default='STUDENT'),
        ),
        migrations.AlterField(
            model_name='campaign', name='applicant_community',
            field=models.CharField(max_length=10, choices=[('STUDENT', 'Student'), ('STAFF', 'Staff'), ('GUEST', 'Guest')], default='STUDENT'),
        ),
        migrations.AlterField(model_name='advertisingsettings', name='founding_offer_enabled', field=models.BooleanField(default=False)),
        migrations.RunPython(set_audience_prices, migrations.RunPython.noop),
    ]
