import pytest


@pytest.mark.django_db
class TestPastoralPrivacy:
    @pytest.fixture
    def pastoral_case(self, branch_a, member_in_branch_a):
        from apps.accounts.models import User
        from apps.pastoral.models import PastoralCase

        pastor = User.objects.create_user(email="pastor@test.com", password="Pass12345!", role="PASTOR", branch=branch_a)
        case = PastoralCase.objects.create(
            branch=branch_a, member=member_in_branch_a, assigned_to=pastor, summary="Confidential matter."
        )
        return case, pastor

    def test_unrelated_member_cannot_list_the_case(self, api_client, branch_a, pastoral_case):
        from apps.accounts.models import User
        from apps.members.models import Member

        case, _ = pastoral_case
        other_user = User.objects.create_user(email="other@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        Member.objects.create(user=other_user, branch=branch_a, first_name="Bob", last_name="Other")

        api_client.force_authenticate(user=other_user)
        response = api_client.get("/api/v1/pastoral/cases/")
        assert response.status_code == 200
        assert response.data["data"] == []

    def test_unrelated_member_cannot_fetch_case_directly(self, api_client, branch_a, pastoral_case):
        from apps.accounts.models import User
        from apps.members.models import Member

        case, _ = pastoral_case
        other_user = User.objects.create_user(email="other2@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        Member.objects.create(user=other_user, branch=branch_a, first_name="Carol", last_name="Other")

        api_client.force_authenticate(user=other_user)
        response = api_client.get(f"/api/v1/pastoral/cases/{case.id}/")
        assert response.status_code == 404

    def test_member_can_see_own_case(self, api_client, member_in_branch_a, pastoral_case):
        case, _ = pastoral_case
        api_client.force_authenticate(user=member_in_branch_a.user)
        response = api_client.get(f"/api/v1/pastoral/cases/{case.id}/")
        assert response.status_code == 200

    def test_assigned_pastor_can_see_case(self, api_client, pastoral_case):
        case, pastor = pastoral_case
        api_client.force_authenticate(user=pastor)
        response = api_client.get(f"/api/v1/pastoral/cases/{case.id}/")
        assert response.status_code == 200

    def test_unassigned_pastoral_role_in_same_branch_can_still_see_it(self, api_client, branch_a, pastoral_case):
        """PASTORAL_ACCESS_ROLES (pastor/chaplain/admin) see all cases in their branch,
        not just ones assigned to them -- pastoral oversight, not per-case siloing."""
        from apps.accounts.models import User

        case, _ = pastoral_case
        other_pastor = User.objects.create_user(email="other_pastor@test.com", password="Pass12345!", role="CHAPLAIN", branch=branch_a)
        api_client.force_authenticate(user=other_pastor)
        response = api_client.get(f"/api/v1/pastoral/cases/{case.id}/")
        assert response.status_code == 200

    def test_finance_officer_cannot_see_pastoral_case(self, api_client, branch_a, pastoral_case):
        from apps.accounts.models import User

        case, _ = pastoral_case
        finance_user = User.objects.create_user(email="finance@test.com", password="Pass12345!", role="FINANCE_OFFICER", branch=branch_a)
        api_client.force_authenticate(user=finance_user)
        response = api_client.get(f"/api/v1/pastoral/cases/{case.id}/")
        assert response.status_code == 404
