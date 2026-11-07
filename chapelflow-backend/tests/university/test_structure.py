import pytest


@pytest.mark.django_db
class TestUniversityStructureIsSeparateFromChapel:
    """Spec section 2: University/College/Department is a separate hierarchy from Chapel Groups."""

    def test_college_and_department_are_not_ministries_groups(self, organization):
        from apps.university.models import College, Department, University
        from apps.ministries.models import Group, GroupType

        university = University.objects.create(organization=organization, name="Test University", slug="test-uni")
        college = College.objects.create(university=university, name="College of Engineering")
        Department.objects.create(college=college, name="Software Engineering")

        # No Group of type DEPARTMENT should ever be required to represent this.
        assert not Group.objects.filter(group_type=GroupType.DEPARTMENT).exists()
        assert College.objects.count() == 1

    def test_university_structure_readable_without_auth(self, api_client, organization):
        """Public self-registration form needs to populate dropdowns pre-login."""
        from apps.university.models import University

        University.objects.create(organization=organization, name="Test University", slug="test-uni")
        response = api_client.get("/api/v1/universities/")
        assert response.status_code == 200

    def test_university_structure_write_requires_permission(self, api_client, organization, member_in_branch_a):
        response_unauth = api_client.post("/api/v1/universities/", {
            "organization": str(organization.id), "name": "New Uni", "slug": "new-uni",
        })
        assert response_unauth.status_code in (401, 403)
