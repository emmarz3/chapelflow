import pytest


@pytest.mark.django_db
class TestVisitorDuplicateDetection:
    def test_duplicates_endpoint_flags_matching_contact(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.visitors.models import Visitor

        Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="08011112222")
        Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="08011112222")
        Visitor.objects.create(branch=branch_a, full_name="Someone Else", phone_number="08033334444")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/duplicates/")
        assert response.status_code == 200
        pairs = response.data["data"]
        assert len(pairs) == 1
        assert len(pairs[0]["candidates"]) == 2

    def test_duplicates_never_matches_on_name_alone(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.visitors.models import Visitor

        Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="08011112222")
        Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="08099998888")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/duplicates/")
        assert response.data["data"] == []

    def test_duplicates_scoped_to_own_branch_only(
        self, api_client, chapel_admin_a, branch_a, branch_b, seed_member_permissions
    ):
        from apps.visitors.models import Visitor

        Visitor.objects.create(branch=branch_a, full_name="A", phone_number="0801")
        Visitor.objects.create(branch=branch_b, full_name="A", phone_number="0801")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/duplicates/")
        assert response.data["data"] == []

    def test_duplicate_detection_never_auto_merges(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        """Detection surfaces candidates only -- both records must still exist untouched afterward."""
        from apps.visitors.models import Visitor

        v1 = Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="0801")
        v2 = Visitor.objects.create(branch=branch_a, full_name="Amaka Eze", phone_number="0801")

        api_client.force_authenticate(user=chapel_admin_a)
        api_client.get("/api/v1/visitors/duplicates/")

        assert Visitor.objects.filter(id__in=[v1.id, v2.id]).count() == 2


@pytest.mark.django_db
class TestVisitorAnalytics:
    def test_analytics_reports_conversion_and_follow_up_rates(
        self, api_client, chapel_admin_a, branch_a, seed_member_permissions
    ):
        from apps.visitors.models import Visitor, VisitorFollowUp, VisitorStatus

        v1 = Visitor.objects.create(branch=branch_a, full_name="A", phone_number="1", status=VisitorStatus.REGISTERED)
        Visitor.objects.create(branch=branch_a, full_name="B", phone_number="2")
        VisitorFollowUp.objects.create(visitor=v1, method="CALL", outcome=VisitorFollowUp.Outcome.REACHED)
        VisitorFollowUp.objects.create(visitor=v1, method="SMS", outcome=VisitorFollowUp.Outcome.PENDING)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/analytics/")
        assert response.status_code == 200
        data = response.data["data"]
        assert data["total_visitors"] == 2
        assert data["converted"] == 1
        assert data["conversion_rate"] == 50.0
        assert data["follow_ups_total"] == 2
        assert data["follow_ups_completed"] == 1
        assert data["follow_up_completion_rate"] == 50.0

    def test_analytics_scoped_to_own_branch(self, api_client, chapel_admin_a, branch_a, branch_b, seed_member_permissions):
        from apps.visitors.models import Visitor

        Visitor.objects.create(branch=branch_a, full_name="A", phone_number="1")
        Visitor.objects.create(branch=branch_b, full_name="B", phone_number="2")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/analytics/")
        assert response.data["data"]["total_visitors"] == 1

    def test_analytics_handles_zero_visitors(self, api_client, chapel_admin_a, seed_member_permissions):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/visitors/analytics/")
        assert response.status_code == 200
        assert response.data["data"]["total_visitors"] == 0
        assert response.data["data"]["conversion_rate"] == 0.0


@pytest.mark.django_db
class TestVisitorScopeAndFieldSecurity:
    def test_staff_cannot_log_visitor_into_another_branch(
        self, api_client, chapel_admin_a, branch_b, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/visitors/", {
            "branch": str(branch_b.id), "full_name": "Cross Branch", "phone_number": "0800",
        }, format="json")
        assert response.status_code == 400

    def test_public_form_drops_cross_branch_invited_by_instead_of_leaking_it(self, api_client, branch_a, branch_b):
        from apps.members.models import Member, MemberQRCode

        other_branch_member = Member.objects.create(branch=branch_b, first_name="Other", last_name="Branch")
        MemberQRCode.objects.get_or_create(member=other_branch_member)

        response = api_client.post("/api/v1/visitors/first-timer-form/", {
            "branch": str(branch_a.id), "full_name": "Someone New", "phone_number": "0801",
            "invited_by": str(other_branch_member.id),
        })
        assert response.status_code == 201

        from apps.visitors.models import Visitor
        visitor = Visitor.objects.get(full_name="Someone New")
        assert visitor.invited_by_id is None

    def test_staff_form_rejects_cross_branch_invited_by(
        self, api_client, chapel_admin_a, branch_a, branch_b, seed_member_permissions
    ):
        from apps.members.models import Member, MemberQRCode

        other_branch_member = Member.objects.create(branch=branch_b, first_name="Other", last_name="Branch")
        MemberQRCode.objects.get_or_create(member=other_branch_member)

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/visitors/", {
            "branch": str(branch_a.id), "full_name": "Staff Logged", "phone_number": "0801",
            "invited_by": str(other_branch_member.id),
        }, format="json")
        assert response.status_code == 400


@pytest.mark.django_db
class TestVisitorPublicEndpointThrottling:
    def test_first_timer_form_action_has_a_throttle_configured(self):
        """
        Config-level check (robust against DRF's settings caching) that
        the public submission action actually gets a throttle instance,
        under the "public" scope, rather than relying on
        DEFAULT_THROTTLE_CLASSES alone.
        """
        from apps.visitors.views import VisitorViewSet

        view = VisitorViewSet()
        view.action = "first_timer_form"
        view.request = None
        throttles = view.get_throttles()
        assert len(throttles) == 1
        assert view.throttle_scope == "public"

    def test_first_timer_form_is_rate_limited_end_to_end(self, api_client, branch_a, settings):
        from rest_framework.throttling import ScopedRateThrottle
        from django.core.cache import cache

        cache.clear()
        original_rates = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {**original_rates, "public": "2/min"}
        try:
            payload = {"branch": str(branch_a.id), "full_name": "Spammer", "phone_number": "0800000000"}
            r1 = api_client.post("/api/v1/visitors/first-timer-form/", payload)
            r2 = api_client.post("/api/v1/visitors/first-timer-form/", payload)
            r3 = api_client.post("/api/v1/visitors/first-timer-form/", payload)
            assert r1.status_code == 201
            assert r2.status_code == 201
            assert r3.status_code == 429
        finally:
            ScopedRateThrottle.THROTTLE_RATES = original_rates
            cache.clear()


@pytest.mark.django_db
class TestVisitorFollowUpReminderTask:
    def test_reminder_task_sends_once_and_is_idempotent(self, branch_a):
        from django.utils import timezone
        from apps.accounts.models import User
        from apps.visitors.models import Visitor, VisitorFollowUp
        from apps.visitors.tasks import send_pending_follow_up_reminders
        from apps.notifications.models import Notification
        from common.constants.roles import Roles

        staff = User.objects.create_user(email="staff@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)
        visitor = Visitor.objects.create(branch=branch_a, full_name="Due Visitor", phone_number="0801")
        follow_up = VisitorFollowUp.objects.create(
            visitor=visitor, method="CALL", assigned_to=staff,
            scheduled_for=timezone.now() - timezone.timedelta(hours=1),
        )

        result = send_pending_follow_up_reminders()
        assert result["reminders_sent"] == 1
        follow_up.refresh_from_db()
        assert follow_up.reminder_sent_at is not None
        assert Notification.objects.filter(recipient=staff).count() == 1

        # Second run must not double-send.
        result2 = send_pending_follow_up_reminders()
        assert result2["reminders_sent"] == 0
        assert Notification.objects.filter(recipient=staff).count() == 1

    def test_reminder_task_skips_unassigned_or_future_follow_ups(self, branch_a):
        from django.utils import timezone
        from apps.visitors.models import Visitor, VisitorFollowUp
        from apps.visitors.tasks import send_pending_follow_up_reminders

        visitor = Visitor.objects.create(branch=branch_a, full_name="Future Visitor", phone_number="0802")
        VisitorFollowUp.objects.create(visitor=visitor, method="CALL", scheduled_for=None)  # unassigned, no schedule
        VisitorFollowUp.objects.create(
            visitor=visitor, method="CALL", scheduled_for=timezone.now() + timezone.timedelta(days=1),
        )

        result = send_pending_follow_up_reminders()
        assert result["reminders_sent"] == 0
