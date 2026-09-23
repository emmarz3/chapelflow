import pytest


@pytest.mark.django_db
class TestFinanceDirectIDAccess:
    """Spec section 10: a user must never gain access to another branch's data by editing an ID in the URL."""

    def _finance_user(self, branch):
        from apps.accounts.models import User
        return User.objects.create_user(email=f"fin-{branch.id}@test.com", password="Pass12345!", role="FINANCE_OFFICER", branch=branch)

    def test_finance_officer_cannot_fetch_another_branchs_giving_record_by_id(self, api_client, branch_a, branch_b):
        from django.utils import timezone

        from apps.finance.models import Giving, GivingCategory

        category = GivingCategory.objects.create(name="Tithe (sweep test)")
        record = Giving.objects.create(branch=branch_b, category=category, amount=5000, source="ONLINE", given_at=timezone.now())

        officer_a = self._finance_user(branch_a)
        api_client.force_authenticate(user=officer_a)
        response = api_client.get(f"/api/v1/giving/{record.id}/")
        assert response.status_code == 404  # filtered out of queryset, not 403 (avoid leaking existence)

    def test_finance_officer_cannot_list_another_branchs_pledges(self, api_client, branch_a, branch_b):
        from apps.finance.models import GivingCategory, Pledge
        from apps.members.models import Member

        category = GivingCategory.objects.create(name="Building Fund (sweep test)")
        member_b = Member.objects.create(branch=branch_b, first_name="Pledge", last_name="Maker")
        Pledge.objects.create(branch=branch_b, member=member_b, category=category, amount_pledged=10000, start_date="2026-01-01")

        officer_a = self._finance_user(branch_a)
        api_client.force_authenticate(user=officer_a)
        response = api_client.get("/api/v1/pledges/")
        assert response.status_code == 200
        assert response.data["data"] == []

    def test_member_role_gets_403_not_404_on_finance_list(self, api_client, member_in_branch_a):
        api_client.force_authenticate(user=member_in_branch_a.user or _attach_user(member_in_branch_a))
        response = api_client.get("/api/v1/giving/")
        assert response.status_code == 403


def _attach_user(member):
    from apps.accounts.models import User
    user = User.objects.create_user(email=f"m-{member.id}@test.com", password="Pass12345!", role="MEMBER", branch=member.branch)
    member.user = user
    member.save(update_fields=["user"])
    return user


@pytest.mark.django_db
class TestEventsDirectIDAccessAndPublicBrowsing:
    def test_event_registration_scoped_to_own_branch(self, api_client, branch_a, branch_b, chapel_admin_a, seed_member_permissions):
        from apps.events.models import Event, EventRegistration, EventSchedule, EventType
        from apps.members.models import Member

        etype = EventType.objects.create(name="Service (sweep test)")
        event_b = Event.objects.create(
            branch=branch_b, event_type=etype, title="Branch B Service",
            start_time="2026-09-01T09:00:00Z", end_time="2026-09-01T11:00:00Z",
        )
        schedule_b = EventSchedule.objects.create(
            event=event_b, occurrence_start="2026-09-01T09:00:00Z", occurrence_end="2026-09-01T11:00:00Z",
        )
        member_b = Member.objects.create(branch=branch_b, first_name="B", last_name="Reg")
        reg = EventRegistration.objects.create(schedule=schedule_b, member=member_b)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/event-registrations/{reg.id}/")
        assert response.status_code == 404

    def test_public_events_endpoint_requires_no_auth(self, api_client, branch_a):
        from apps.events.models import Event, EventType

        etype = EventType.objects.create(name="Public Service (sweep test)")
        Event.objects.create(
            branch=branch_a, event_type=etype, title="Open to All",
            start_time="2026-09-01T09:00:00Z", end_time="2026-09-01T11:00:00Z", is_public=True,
        )
        Event.objects.create(
            branch=branch_a, event_type=etype, title="Members Only",
            start_time="2026-09-01T09:00:00Z", end_time="2026-09-01T11:00:00Z", is_public=False,
        )

        response = api_client.get("/api/v1/events/public/")
        assert response.status_code == 200
        titles = {e["title"] for e in response.data.get("data", response.data.get("results", []))}
        assert "Open to All" in titles
        assert "Members Only" not in titles

    def test_events_list_still_requires_auth_and_permission(self, api_client):
        response = api_client.get("/api/v1/events/")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestUploadsScopingAndDirectID:
    def test_upload_list_scoped_to_own_branch(self, api_client, branch_a, branch_b, chapel_admin_a):
        from apps.uploads.models import Upload

        Upload.objects.create(branch=branch_b, category="OTHER", original_filename="x.pdf", file_url="https://x/x.pdf", size_bytes=10)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/uploads/")
        assert response.status_code == 200
        assert response.data["data"] == []

    def test_upload_direct_id_from_other_branch_404s(self, api_client, branch_a, branch_b, chapel_admin_a):
        from apps.uploads.models import Upload

        upload = Upload.objects.create(branch=branch_b, category="OTHER", original_filename="x.pdf", file_url="https://x/x.pdf", size_bytes=10)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/uploads/{upload.id}/")
        assert response.status_code == 404
