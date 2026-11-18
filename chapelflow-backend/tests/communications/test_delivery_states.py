import pytest


@pytest.mark.django_db
class TestNotificationDeliveryStates:
    """
    Spec section 13: "Do not mark an SMS/push delivery as 'sent' when the
    provider is only stubbed." Email uses Django's locmem backend in test
    settings (a real send), SMS/push use the stub providers.
    """

    def _notification(self, branch_a, channel, **kwargs):
        from apps.accounts.models import User
        from apps.notifications.models import Notification

        user = User.objects.create_user(
            email=f"notif-{channel.lower()}@test.com", password="Pass12345!", role="MEMBER",
            branch=branch_a, phone_number="08012345678",
        )
        return Notification.objects.create(recipient=user, channel=channel, title="Test", body="Body", **kwargs)

    def test_email_delivery_is_marked_sent(self, branch_a):
        from apps.notifications.models import NotificationStatus
        from apps.notifications.tasks import deliver_notification

        notification = self._notification(branch_a, "EMAIL")
        deliver_notification(str(notification.id))

        notification.refresh_from_db()
        assert notification.status == NotificationStatus.SENT
        assert notification.sent_at is not None

    def test_sms_delivery_is_marked_stubbed_not_sent(self, branch_a):
        from apps.notifications.models import NotificationStatus
        from apps.notifications.tasks import deliver_notification

        notification = self._notification(branch_a, "SMS")
        deliver_notification(str(notification.id))

        notification.refresh_from_db()
        assert notification.status == NotificationStatus.STUBBED
        assert notification.status != NotificationStatus.SENT
        assert notification.sent_at is None

    def test_push_delivery_is_marked_stubbed_not_sent(self, branch_a):
        from apps.notifications.models import NotificationStatus
        from apps.notifications.tasks import deliver_notification

        notification = self._notification(branch_a, "PUSH")
        deliver_notification(str(notification.id))

        notification.refresh_from_db()
        assert notification.status == NotificationStatus.STUBBED

    def test_mark_notification_delivered_only_transitions_from_sent(self, branch_a):
        from apps.notifications.models import NotificationStatus
        from apps.notifications.tasks import mark_notification_delivered

        stubbed = self._notification(branch_a, "SMS", status=NotificationStatus.STUBBED)
        mark_notification_delivered(str(stubbed.id))
        stubbed.refresh_from_db()
        assert stubbed.status == NotificationStatus.STUBBED  # unchanged — was never really sent

        sent = self._notification(branch_a, "EMAIL", status=NotificationStatus.SENT)
        result = mark_notification_delivered(str(sent.id))
        sent.refresh_from_db()
        assert sent.status == NotificationStatus.DELIVERED
        assert result["updated"] is True


@pytest.mark.django_db
class TestAnnouncementDeliveryStatusRollup:
    def test_delivery_summary_aggregates_by_status(self, branch_a):
        from apps.accounts.models import User
        from apps.communications.models import Announcement
        from apps.communications.tasks import get_announcement_delivery_summary
        from apps.notifications.models import Notification, NotificationStatus

        announcement = Announcement.objects.create(
            branch=branch_a, title="Sunday Service", body="Join us", publish_at="2026-09-01T09:00:00Z",
        )
        u1 = User.objects.create_user(email="d1@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)
        u2 = User.objects.create_user(email="d2@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)

        Notification.objects.create(
            recipient=u1, channel="EMAIL", title="x", body="y",
            status=NotificationStatus.SENT, source_announcement=announcement,
        )
        Notification.objects.create(
            recipient=u2, channel="SMS", title="x", body="y",
            status=NotificationStatus.STUBBED, source_announcement=announcement,
        )

        summary = get_announcement_delivery_summary(announcement.id)
        assert summary["total"] == 2
        assert summary["by_status"]["SENT"] == 1
        assert summary["by_status"]["STUBBED"] == 1
        assert summary["by_status"]["DELIVERED"] == 0

    def test_delivery_status_endpoint_scoped_and_permissioned(self, api_client, chapel_admin_a, branch_a, seed_member_permissions):
        from apps.communications.models import Announcement

        announcement = Announcement.objects.create(
            branch=branch_a, title="Test Announcement", body="Body", publish_at="2026-09-01T09:00:00Z",
        )
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/communications/announcements/{announcement.id}/delivery-status/")
        assert response.status_code == 200
        assert response.data["data"]["total"] == 0

    def test_delivery_status_endpoint_respects_branch_scoping(self, api_client, chapel_admin_a, branch_b, seed_member_permissions):
        from apps.communications.models import Announcement

        other_branch_announcement = Announcement.objects.create(
            branch=branch_b, title="Other Branch", body="Body", publish_at="2026-09-01T09:00:00Z",
        )
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/communications/announcements/{other_branch_announcement.id}/delivery-status/")
        assert response.status_code == 404
