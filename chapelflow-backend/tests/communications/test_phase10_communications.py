import hashlib
import hmac
import json

import pytest
from django.utils import timezone


def _grant(role, *codes):
    from apps.accounts.models import Permission, RolePermission

    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)


@pytest.fixture
def fellowship_leader_setup(branch_a):
    from apps.groups.models import GroupMembership, GroupRole
    from apps.members.models import Member
    from apps.ministries.models import Group, GroupType

    led = Group.objects.create(branch=branch_a, name="Led Fellowship", group_type=GroupType.FELLOWSHIP)
    other = Group.objects.create(branch=branch_a, name="Other Fellowship", group_type=GroupType.FELLOWSHIP)
    leader_member = Member.objects.create(branch=branch_a, first_name="Fola", last_name="Leads")
    GroupMembership.objects.create(member=leader_member, group=led, role=GroupRole.LEADER)
    return {"led": led, "other": other, "leader_member": leader_member}


@pytest.fixture
def fellowship_leader_user(branch_a, make_user, fellowship_leader_setup):
    from common.constants.roles import PermissionCodes

    _grant(
        "FELLOWSHIP_LEADER", PermissionCodes.COMMUNICATIONS_VIEW,
        PermissionCodes.COMMUNICATIONS_CREATE, PermissionCodes.COMMUNICATIONS_SEND,
    )
    user = make_user(role="FELLOWSHIP_LEADER", branch=branch_a, email="fellow@test.com")
    member = fellowship_leader_setup["leader_member"]
    member.user = user
    member.save(update_fields=["user"])
    return user


@pytest.mark.django_db
class TestAudienceEscalationPrevention:
    """
    Spec section 13, verbatim: "A Fellowship Leader must not be able to
    turn a Fellowship campaign into a university-wide campaign by
    changing a request parameter." This is the flagship Phase 10
    authorization requirement.
    """

    def test_fellowship_leader_cannot_target_everyone(
        self, api_client, fellowship_leader_user, fellowship_leader_setup, branch_a
    ):
        api_client.force_authenticate(user=fellowship_leader_user)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {
                "branch": str(branch_a.id), "title": "Campus Wide", "body": "Hi all",
                "audience_type": "EVERYONE", "publish_at": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == 400
        assert "audience_type" in response.data["errors"]

    def test_fellowship_leader_cannot_target_staff_community(
        self, api_client, fellowship_leader_user, branch_a
    ):
        api_client.force_authenticate(user=fellowship_leader_user)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {
                "branch": str(branch_a.id), "title": "Staff blast", "body": "Hi",
                "audience_type": "STAFF_COMMUNITY", "publish_at": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == 400

    def test_fellowship_leader_cannot_target_a_fellowship_they_dont_lead(
        self, api_client, fellowship_leader_user, fellowship_leader_setup, branch_a
    ):
        api_client.force_authenticate(user=fellowship_leader_user)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {
                "branch": str(branch_a.id), "title": "Not mine", "body": "Hi",
                "audience_type": "FELLOWSHIP", "target_groups": [str(fellowship_leader_setup["other"].id)],
                "publish_at": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == 400
        assert "target_groups" in response.data["errors"]

    def test_fellowship_leader_can_target_own_fellowship(
        self, api_client, fellowship_leader_user, fellowship_leader_setup, branch_a
    ):
        api_client.force_authenticate(user=fellowship_leader_user)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {
                "branch": str(branch_a.id), "title": "My Fellowship", "body": "Hi",
                "audience_type": "FELLOWSHIP", "target_groups": [str(fellowship_leader_setup["led"].id)],
                "publish_at": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == 201

    def test_cross_branch_group_targeting_rejected_for_chapel_admin(
        self, api_client, chapel_admin_a, seed_member_permissions, branch_a, branch_b
    ):
        from apps.ministries.models import Group, GroupType

        foreign_group = Group.objects.create(branch=branch_b, name="Foreign", group_type=GroupType.UNIT)
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {
                "branch": str(branch_a.id), "title": "Leak", "body": "Hi",
                "audience_type": "CUSTOM", "target_groups": [str(foreign_group.id)],
                "publish_at": timezone.now().isoformat(),
            },
            format="json",
        )
        assert response.status_code == 400
        assert "target_groups" in response.data["errors"]

    def test_cannot_create_announcement_in_a_branch_you_dont_access(
        self, api_client, chapel_admin_a, seed_member_permissions, branch_b
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {"branch": str(branch_b.id), "title": "Cross branch", "body": "Hi", "publish_at": timezone.now().isoformat()},
            format="json",
        )
        assert response.status_code == 400
        assert "branch" in response.data["errors"]


@pytest.mark.django_db
class TestCampaignLifecycle:
    def test_past_publish_at_is_queued_immediately(self, api_client, chapel_admin_a, seed_member_permissions, branch_a):
        from apps.communications.models import Announcement, CampaignStatus

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(
            "/api/v1/communications/announcements/",
            {"branch": str(branch_a.id), "title": "Now", "body": "Hi", "publish_at": timezone.now().isoformat()},
            format="json",
        )
        assert response.status_code == 201
        announcement = Announcement.objects.get(id=response.data["data"]["id"])
        # CELERY_TASK_ALWAYS_EAGER in test settings means the dispatch task
        # already ran synchronously by the time we check.
        assert announcement.status == CampaignStatus.COMPLETED

    def test_future_publish_at_is_scheduled_via_eta(self, api_client, chapel_admin_a, seed_member_permissions, branch_a):
        """
        CELERY_TASK_ALWAYS_EAGER (test settings) executes tasks immediately
        and ignores `eta`, so we can't observe "hasn't run yet" via status
        here the way a real worker would show it. Instead we verify the
        view actually requests eta-scheduling for a future publish_at,
        which is what makes a real (non-eager) worker actually wait.
        """
        from unittest.mock import patch

        from apps.communications import views as communications_views

        future = timezone.now() + timezone.timedelta(days=3)
        api_client.force_authenticate(user=chapel_admin_a)
        with patch.object(communications_views.dispatch_announcement, "apply_async") as mock_apply_async:
            response = api_client.post(
                "/api/v1/communications/announcements/",
                {"branch": str(branch_a.id), "title": "Later", "body": "Hi", "publish_at": future.isoformat()},
                format="json",
            )
        assert response.status_code == 201
        assert mock_apply_async.call_count == 1
        assert mock_apply_async.call_args.kwargs["eta"] is not None
        from apps.communications.models import Announcement, CampaignStatus
        announcement = Announcement.objects.get(id=response.data["data"]["id"])
        assert announcement.status == CampaignStatus.SCHEDULED

    def test_send_now_forces_dispatch_of_a_scheduled_campaign(
        self, api_client, chapel_admin_a, seed_member_permissions, branch_a
    ):
        from apps.communications.models import Announcement, CampaignStatus

        future = timezone.now() + timezone.timedelta(days=3)
        announcement = Announcement.objects.create(branch=branch_a, title="Later", body="Hi", publish_at=future)
        announcement.status = CampaignStatus.SCHEDULED
        announcement.save(update_fields=["status"])

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post(f"/api/v1/communications/announcements/{announcement.id}/send-now/")
        assert response.status_code == 200
        announcement.refresh_from_db()
        assert announcement.status == CampaignStatus.COMPLETED

    def test_repeated_dispatch_of_completed_campaign_is_a_noop(self, branch_a):
        from apps.communications.models import Announcement, CampaignStatus
        from apps.communications.tasks import dispatch_announcement
        from apps.notifications.models import Notification

        announcement = Announcement.objects.create(
            branch=branch_a, title="X", body="Y", publish_at=timezone.now(), status=CampaignStatus.COMPLETED,
        )
        dispatch_announcement(str(announcement.id))
        assert Notification.objects.filter(source_announcement=announcement).count() == 0


@pytest.mark.django_db
class TestCommunicationPreferences:
    def test_opted_out_member_receives_no_notification(self, branch_a):
        from apps.accounts.models import User
        from apps.communications.models import Announcement, CommunicationPreference
        from apps.communications.tasks import dispatch_announcement
        from apps.members.models import Member
        from apps.notifications.models import Notification

        u1 = User.objects.create_user(email="opted-in@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        m1 = Member.objects.create(user=u1, branch=branch_a, first_name="In", last_name="Person")
        u2 = User.objects.create_user(email="opted-out@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        m2 = Member.objects.create(user=u2, branch=branch_a, first_name="Out", last_name="Person")
        CommunicationPreference.objects.create(member=m2, announcements_enabled=False)

        announcement = Announcement.objects.create(
            branch=branch_a, title="Blast", body="Hi", publish_at=timezone.now(), audience_type="EVERYONE",
        )
        dispatch_announcement(str(announcement.id))

        recipients = set(Notification.objects.filter(source_announcement=announcement).values_list("recipient_id", flat=True))
        assert u1.id in recipients
        assert u2.id not in recipients

    def test_channel_specific_optout_only_blocks_that_channel(self, branch_a):
        from apps.accounts.models import User
        from apps.communications.models import Announcement, CommunicationPreference
        from apps.communications.tasks import dispatch_announcement
        from apps.members.models import Member
        from apps.notifications.models import Notification

        user = User.objects.create_user(
            email="sms-off@test.com", password="Pass12345!", role="MEMBER", branch=branch_a, phone_number="08011112222",
        )
        member = Member.objects.create(user=user, branch=branch_a, first_name="Sms", last_name="Off")
        CommunicationPreference.objects.create(member=member, sms_enabled=False)

        announcement = Announcement.objects.create(
            branch=branch_a, title="Multi", body="Hi", publish_at=timezone.now(),
            audience_type="EVERYONE", channels=["EMAIL", "SMS"],
        )
        dispatch_announcement(str(announcement.id))

        channels_received = set(
            Notification.objects.filter(source_announcement=announcement, recipient=user).values_list("channel", flat=True)
        )
        assert "EMAIL" in channels_received
        assert "SMS" not in channels_received

    def test_member_can_only_manage_own_preferences(self, api_client, branch_a, make_user):
        from apps.members.models import Member

        user_a = make_user(role="MEMBER", branch=branch_a, email="prefowner@test.com")
        member_a = Member.objects.create(user=user_a, branch=branch_a, first_name="Pref", last_name="Owner")
        user_b = make_user(role="MEMBER", branch=branch_a, email="otherpref@test.com")
        member_b = Member.objects.create(user=user_b, branch=branch_a, first_name="Other", last_name="Pref")

        from apps.communications.models import CommunicationPreference
        pref_b = CommunicationPreference.objects.create(member=member_b, sms_enabled=False)

        from common.constants.roles import PermissionCodes
        _grant("MEMBER", PermissionCodes.COMMUNICATIONS_VIEW)

        api_client.force_authenticate(user=user_a)
        response = api_client.get(f"/api/v1/communications/preferences/{pref_b.id}/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestNotificationDeliveryWebhook:
    def _sign(self, secret, body: bytes) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature_marks_delivered_and_is_idempotent(self, api_client, branch_a, settings):
        from apps.accounts.models import User
        from apps.notifications.models import Notification, NotificationStatus

        settings.NOTIFICATION_WEBHOOK_SECRET = "test-secret"
        user = User.objects.create_user(email="webhook@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        notification = Notification.objects.create(
            recipient=user, channel="EMAIL", title="x", body="y", status=NotificationStatus.SENT,
        )

        payload = json.dumps({"notification_id": str(notification.id), "event": "delivered"}).encode()
        signature = self._sign("test-secret", payload)

        resp = api_client.post(
            "/api/v1/notifications/webhook/", data=payload, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
        assert resp.status_code == 200
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.DELIVERED

        # Re-delivery of the same event -> idempotent no-op, still DELIVERED.
        resp2 = api_client.post(
            "/api/v1/notifications/webhook/", data=payload, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
        assert resp2.status_code == 200
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.DELIVERED

    def test_invalid_signature_rejected(self, api_client, branch_a, settings):
        from apps.accounts.models import User
        from apps.notifications.models import Notification, NotificationStatus

        settings.NOTIFICATION_WEBHOOK_SECRET = "test-secret"
        user = User.objects.create_user(email="webhook2@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        notification = Notification.objects.create(
            recipient=user, channel="EMAIL", title="x", body="y", status=NotificationStatus.SENT,
        )
        payload = json.dumps({"notification_id": str(notification.id), "event": "delivered"}).encode()

        resp = api_client.post(
            "/api/v1/notifications/webhook/", data=payload, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="wrong-signature",
        )
        assert resp.status_code == 400
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.SENT

    def test_no_secret_configured_fails_closed(self, api_client, branch_a, settings):
        from apps.accounts.models import User
        from apps.notifications.models import Notification, NotificationStatus

        settings.NOTIFICATION_WEBHOOK_SECRET = ""
        user = User.objects.create_user(email="webhook3@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        notification = Notification.objects.create(
            recipient=user, channel="EMAIL", title="x", body="y", status=NotificationStatus.SENT,
        )
        payload = json.dumps({"notification_id": str(notification.id), "event": "delivered"}).encode()

        resp = api_client.post(
            "/api/v1/notifications/webhook/", data=payload, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE="anything",
        )
        assert resp.status_code == 400

    def test_stubbed_notification_not_falsely_marked_delivered_by_webhook(self, api_client, branch_a, settings):
        """A provider callback can't fast-forward a STUBBED (never really sent) notification to DELIVERED."""
        from apps.accounts.models import User
        from apps.notifications.models import Notification, NotificationStatus

        settings.NOTIFICATION_WEBHOOK_SECRET = "test-secret"
        user = User.objects.create_user(email="webhook4@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        notification = Notification.objects.create(
            recipient=user, channel="SMS", title="x", body="y", status=NotificationStatus.STUBBED,
        )
        payload = json.dumps({"notification_id": str(notification.id), "event": "delivered"}).encode()
        signature = self._sign("test-secret", payload)

        resp = api_client.post(
            "/api/v1/notifications/webhook/", data=payload, content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )
        assert resp.status_code == 200
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.STUBBED
