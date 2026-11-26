from django.db import migrations


def enable_dashboard_ads(apps, schema_editor):
    Program = apps.get_model('advertising', 'AdSubscriptionProgram')
    Campaign = apps.get_model('advertising', 'Campaign')
    for program in Program.objects.filter(code__in=['campus-brand', 'featured-brand']):
        program.placements = ['home', 'dashboard']
        program.description = 'Sponsored placement on the ChapelFlow homepage and in a small dashboard popup.'
        program.save(update_fields=['placements', 'description'])
    # Existing paid placements keep their agreed homepage/events entitlement.
    # Dashboard exposure is an added benefit, never a replacement.
    for campaign in Campaign.objects.exclude(placements_snapshot__isnull=True).iterator():
        placements = list(campaign.placements_snapshot or [])
        if 'dashboard' not in placements:
            campaign.placements_snapshot = placements + ['dashboard']
            campaign.save(update_fields=['placements_snapshot'])


class Migration(migrations.Migration):
    dependencies = [('advertising', '0005_audience_pricing')]
    operations = [migrations.RunPython(enable_dashboard_ads, migrations.RunPython.noop)]
