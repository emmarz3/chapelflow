import pytest


@pytest.mark.django_db
class TestVisitorPipeline:
    """Spec section 4: Visitor -> First-Timer Form -> Visitor Record -> Follow-Up -> Optional Full Registration -> Member."""

    def test_public_can_submit_first_timer_form(self, api_client, branch_a):
        response = api_client.post("/api/v1/visitors/first-timer-form/", {
            "branch": str(branch_a.id),
            "full_name": "Tunde Bello",
            "phone_number": "08012345678",
            "how_heard": "Friend invited me",
        })
        assert response.status_code == 201

        from apps.visitors.models import Visitor
        visitor = Visitor.objects.get(full_name="Tunde Bello")
        assert visitor.status == "NEW"

    def test_first_timer_form_requires_contact_info(self, api_client, branch_a):
        response = api_client.post("/api/v1/visitors/first-timer-form/", {
            "branch": str(branch_a.id), "full_name": "No Contact Info",
        })
        assert response.status_code == 400

    def test_staff_can_log_follow_up(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.visitors.models import Visitor

        visitor = Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="0800000000")
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/visitors/{visitor.id}/follow-up/", {
            "method": "CALL", "outcome": "REACHED", "notes": "Invited to next service",
        })
        assert response.status_code == 201

        visitor.refresh_from_db()
        assert visitor.status == "CONTACTED"

    def test_convert_visitor_creates_member_and_marks_registered(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        from apps.visitors.models import Visitor

        visitor = Visitor.objects.create(
            branch=branch_a, full_name="Chinedu Okoro", phone_number="0811111111", email="chinedu@test.com",
        )
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/visitors/{visitor.id}/convert/", {})
        assert response.status_code == 200

        visitor.refresh_from_db()
        assert visitor.status == "REGISTERED"
        assert visitor.converted_member is not None

        from apps.members.models import Member
        member = Member.objects.get(id=visitor.converted_member_id)
        assert member.first_name == "Chinedu"
        assert member.branch_id == branch_a.id

    def test_cannot_convert_already_converted_visitor(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        from apps.visitors.models import Visitor

        visitor = Visitor.objects.create(branch=branch_a, full_name="Twice Converted", phone_number="0822222222")
        api_client.force_authenticate(user=chapel_admin_a)
        api_client.post(f"/api/v1/visitors/{visitor.id}/convert/", {})
        response = api_client.post(f"/api/v1/visitors/{visitor.id}/convert/", {})
        assert response.status_code == 400

    def test_visitors_are_branch_scoped(self, api_client, chapel_admin_b, branch_a, seed_member_permissions):
        from apps.visitors.models import Visitor

        Visitor.objects.create(branch=branch_a, full_name="Branch A Visitor", phone_number="0833333333")
        api_client.force_authenticate(user=chapel_admin_b)
        response = api_client.get("/api/v1/visitors/")
        assert response.status_code == 200
        assert response.data["data"] == []
