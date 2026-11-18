import pytest
from django.contrib import admin

from apps.members.models import (
    AcademicLevel,
    JupebStudent,
    Level100Student,
    Level200Student,
    Level300Student,
    Level400Student,
    Level500Student,
    Level600Student,
    Member,
)


@pytest.mark.django_db
def test_admin_level_sections_show_only_students_in_the_selected_level(rf, super_admin, branch_a):
    models_by_level = {
        AcademicLevel.JUPEB: JupebStudent,
        AcademicLevel.LEVEL_100: Level100Student,
        AcademicLevel.LEVEL_200: Level200Student,
        AcademicLevel.LEVEL_300: Level300Student,
        AcademicLevel.LEVEL_400: Level400Student,
        AcademicLevel.LEVEL_500: Level500Student,
        AcademicLevel.LEVEL_600: Level600Student,
    }
    expected_ids = {}
    for level in models_by_level:
        member = Member.objects.create(
            branch=branch_a,
            first_name=level,
            last_name="Student",
            community="STUDENT",
            academic_level=level,
        )
        expected_ids[level] = member.id

    Member.objects.create(
        branch=branch_a,
        first_name="Staff",
        last_name="Member",
        community="STAFF",
        academic_level=AcademicLevel.LEVEL_100,
    )

    request = rf.get("/admin/members/")
    request.user = super_admin
    for level, proxy_model in models_by_level.items():
        queryset = admin.site._registry[proxy_model].get_queryset(request)
        assert list(queryset.values_list("id", flat=True)) == [expected_ids[level]]
