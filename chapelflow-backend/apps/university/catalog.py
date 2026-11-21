"""Chrisland University's academic catalogue for student registration.

Current college/faculty pages and Academic Planning list, checked November 2026.
The JUPEB entry represents foundation students without an undergraduate major.
"""

PROGRAMMES_BY_COLLEGE = {
    "College of Arts, Management and Social Sciences": (
        "Accounting", "Banking and Finance", "Business Administration",
        "Criminology and Security Studies", "Economics", "English",
        "International Relations and Diplomacy", "Mass Communication",
        "Political Science", "Psychology",
    ),
    "College of Natural and Applied Sciences": (
        "Biochemistry", "Computer Science", "Cybersecurity", "Industrial Chemistry",
        "Mathematics", "Microbiology", "Molecular Biology and Biotechnology",
        "Software Engineering",
    ),
    "College of Basic Medical Sciences": (
        "Medical Laboratory Science", "Physiotherapy", "Public Health",
    ),
    "Faculty of Nursing Sciences": ("Nursing Science",),
    "College of Law": ("Law",),
    "Foundation Programmes": ("JUPEB",),
    "Postgraduate College": ("Postgraduate Studies",),
}


def ensure_chrisland_programmes():
    """Add missing entries without changing existing university records."""
    from apps.organizations.models import Organization
    from .models import College, Department, University

    organization = Organization.objects.filter(slug="chrisland").first()
    if not organization:
        return
    university, _ = University.objects.get_or_create(
        slug="chrisland-university",
        defaults={"organization": organization, "name": "Chrisland University"},
    )
    for college_name, programmes in PROGRAMMES_BY_COLLEGE.items():
        college, _ = College.objects.get_or_create(
            university=university, name=college_name,
        )
        for programme in programmes:
            Department.objects.get_or_create(college=college, name=programme)
