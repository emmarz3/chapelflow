import os

from django.db import migrations
from django.utils import timezone


# Snapshot the existing chapel catalog for databases initialized at this revision.
GROUPS = (
    ("UNIT", "Intercessory"),
    ("UNIT", "Treasurer"),
    ("UNIT", "Chapel Protocol"),
    ("UNIT", "Music"),
    ("UNIT", "Instrumentalist"),
    ("UNIT", "Ushering"),
    ("UNIT", "Sanctuary Keepers"),
    ("UNIT", "Media & ICT"),
    ("UNIT", "Social Media"),
    ("UNIT", "Library"),
    ("UNIT", "Drama Team"),
    ("UNIT", "Technical & Sound"),
    ("FELLOWSHIP", "Love Campus Fellowship"),
    ("FELLOWSHIP", "Truth Campus Fellowship"),
    ("FELLOWSHIP", "Favour Campus Fellowship"),
    ("FELLOWSHIP", "Integrity Campus Fellowship"),
    ("FELLOWSHIP", "Righteousness Campus Fellowship"),
    ("FELLOWSHIP", "Mercy Campus Fellowship"),
    ("FELLOWSHIP", "Excellence Campus Fellowship"),
    ("FELLOWSHIP", "Grace Campus Fellowship"),
    ("FELLOWSHIP", "Outstanding Campus Fellowship"),
    ("FELLOWSHIP", "Peace Campus Fellowship"),
)

# Match the initial pages that migration 0002 seeds for preexisting chapels.
PAGES = (
    ("home", "A chapel community for every part of university life", "Join us as we worship, grow, and serve together at Chrisland University Chapel, Abeokuta."),
    ("about", "A community rooted in faith and service", "Chrisland University Chapel serves students and staff through worship, care, formation, and service."),
    ("events", "Events and gatherings", "Find worship services, fellowships, and campus gatherings."),
    ("giving", "Give with purpose", "Support approved chapel programmes through the institution's configured giving channels."),
    ("mission", "Grounded in faith. Prepared for service", "Our mission is to cultivate Christ-centred lives through worship, discipleship, fellowship, and service."),
    ("leadership", "Serving with wisdom and care", "Meet the pastoral and student leaders supporting the chapel community."),
    ("services", "Make room for worship in your week", "Find the chapel's approved worship and prayer gathering information."),
    ("contact", "We are here to listen and help", "Contact the chapel office or plan a visit to the Abeokuta campus."),
    ("faq", "Helpful answers before you arrive", "Answers about chapel services, student participation, attendance, and ChapelFlow."),
)


def seed_fresh_chapel(apps, schema_editor):
    # Automatic bootstrap is opt-in for a fresh Railway installation.
    if os.environ.get("CHAPELFLOW_BOOTSTRAP_FRESH") != "1":
        return

    alias = schema_editor.connection.alias
    Organization = apps.get_model("organizations", "Organization")
    organizations = Organization.objects.using(alias)
    if organizations.exists():
        return

    organization, created = organizations.get_or_create(
        slug="chrisland", defaults={"name": "Chrisland University"}
    )
    if not created:
        return

    Branch = apps.get_model("organizations", "Branch")
    Group = apps.get_model("ministries", "Group")
    ContentEntry = apps.get_model("operations", "ContentEntry")

    branch = Branch.objects.using(alias).create(
        organization=organization,
        name="Chrisland University Chapel",
        branch_type="CHAPEL",
        city="Abeokuta",
        country="Nigeria",
    )
    Group.objects.using(alias).bulk_create([
        Group(
            branch=branch,
            name=name,
            group_type=group_type,
            description=(
                "Custody and preparation team for ChapelFlow inventory."
                if name == "Chapel Protocol"
                else ""
            ),
        )
        for group_type, name in GROUPS
    ])

    now = timezone.now()
    ContentEntry.objects.using(alias).bulk_create([
        ContentEntry(
            branch=branch,
            slug=slug,
            content_type="PAGE",
            title=title,
            summary=body,
            details=body,
            status="PUBLISHED",
            published_at=now,
            metadata={"seeded_initial_page": True},
        )
        for slug, title, body in PAGES
    ])


class Migration(migrations.Migration):
    dependencies = [
        ("ministries", "0005_group_unique_group_name_per_branch_type"),
        ("operations", "0006_homepage_content"),
    ]

    # A chapel created here can later own live records. Keep it when rolling back.
    operations = [migrations.RunPython(seed_fresh_chapel, migrations.RunPython.noop)]
