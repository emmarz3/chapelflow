from django.db import migrations


# Snapshot of the official college/faculty catalogue for this migration.
PROGRAMMES = {
    "College of Arts, Management and Social Sciences": (
        "Accounting", "Banking and Finance", "Business Administration",
        "Criminology and Security Studies", "Economics", "English",
        "International Relations and Diplomacy", "Mass Communication", "Political Science", "Psychology",
    ),
    "College of Natural and Applied Sciences": (
        "Biochemistry", "Computer Science", "Cybersecurity", "Industrial Chemistry",
        "Mathematics", "Microbiology", "Molecular Biology and Biotechnology", "Software Engineering",
    ),
    "College of Basic Medical Sciences": ("Medical Laboratory Science", "Physiotherapy", "Public Health"),
    "Faculty of Nursing Sciences": ("Nursing Science",),
    "College of Law": ("Law",),
    "Foundation Programmes": ("JUPEB",),
}


def seed_programmes(apps, schema_editor):
    alias = schema_editor.connection.alias
    Organization = apps.get_model("organizations", "Organization")
    University = apps.get_model("university", "University")
    College = apps.get_model("university", "College")
    Department = apps.get_model("university", "Department")
    organization = Organization.objects.using(alias).filter(slug="chrisland").first()
    if not organization:
        return  # bootstrap_chapel seeds the catalogue when it creates the chapel.
    university, _ = University.objects.using(alias).get_or_create(
        slug="chrisland-university",
        defaults={"organization": organization, "name": "Chrisland University"},
    )
    for college_name, programmes in PROGRAMMES.items():
        college, _ = College.objects.using(alias).get_or_create(
            university=university, name=college_name,
        )
        for programme in programmes:
            Department.objects.using(alias).get_or_create(college=college, name=programme)


class Migration(migrations.Migration):
    dependencies = [
        ("university", "0002_alter_university_options"),
        ("operations", "0007_seed_fresh_chapel"),
    ]

    operations = [migrations.RunPython(seed_programmes, migrations.RunPython.noop)]
