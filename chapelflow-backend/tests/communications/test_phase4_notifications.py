from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.communications.models import CommunicationPreference
from apps.members.models import Member
from apps.notifications.models import Notification, NotificationCategory, NotificationChannel, NotificationStatus
from apps.notifications.preferences import queue_notification
from apps.notifications.tasks import deliver_notification


@pytest.fixture
def accounts(make_user, branch_a, branch_b):
    owner = make_user(email="notify-owner@chapelflow.test", branch=branch_a)
    other = make_user(email="notify-other@chapelflow.test", branch=branch_b)
    member = Member.objects.create(branch=branch_a, user=owner, first_name="Notify", last_name="Owner")
    return owner, other, member


@pytest.mark.django_db
def test_self_service_preferences_cover_categories_channels_and_staff(api_client, accounts, make_user, branch_a):
    owner, _, member = accounts
    api_client.force_authenticate(user=owner)
    response = api_client.get("/api/v1/communications/preferences/me/")
    assert response.status_code == 200
    assert response.data["data"]["member"] == member.id
    changed = api_client.patch("/api/v1/communications/preferences/me/", {
        "events_enabled": False, "fellowship_enabled": False, "email_enabled": False,
        "master_enabled": False, "in_app_enabled": False,
    }, format="json")
    assert changed.status_code == 200
    preference = CommunicationPreference.objects.get(member=member)
    assert preference.user_id == owner.id
    assert not preference.events_enabled and not preference.master_enabled and not preference.email_enabled
    staff = make_user(email="notify-staff@chapelflow.test", branch=branch_a, role="CHAPLAIN")
    api_client.force_authenticate(user=staff)
    assert api_client.get("/api/v1/communications/preferences/me/").status_code == 200
    assert CommunicationPreference.objects.get(user=staff).member_id is None


@pytest.mark.django_db
def test_disabled_category_and_master_create_no_notification(accounts):
    owner, _, member = accounts
    preference = CommunicationPreference.objects.create(user=owner, member=member, events_enabled=False)
    assert queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.EMAIL, title="Event", body="Soon") is None
    assert Notification.objects.count() == 0
    preference.events_enabled = True
    preference.master_enabled = False
    preference.save()
    assert queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.IN_APP, title="Event", body="Soon") is None
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_late_opt_out_skips_queued_delivery_and_inbox(api_client, accounts):
    owner, _, member = accounts
    preference = CommunicationPreference.objects.create(user=owner, member=member)
    notification = queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.EMAIL, title="Event", body="Soon")
    preference.events_enabled = False
    preference.save()
    with patch("apps.notifications.tasks.email_provider.send") as send:
        assert deliver_notification(str(notification.id))["status"] == "skipped"
        send.assert_not_called()
    notification.refresh_from_db()
    assert notification.status == NotificationStatus.SKIPPED
    api_client.force_authenticate(user=owner)
    assert api_client.get("/api/v1/notifications/").data["data"] == []
    assert api_client.get("/api/v1/notifications/unread-count/").data["data"]["count"] == 0


@pytest.mark.django_db
def test_idempotent_delivery_and_accurate_read_counts(api_client, accounts):
    owner, other, _ = accounts
    first = queue_notification(recipient=owner, category=NotificationCategory.ANNOUNCEMENT, channel=NotificationChannel.EMAIL, title="Notice", body="Text", idempotency_key="notice-1")
    second = queue_notification(recipient=owner, category=NotificationCategory.ANNOUNCEMENT, channel=NotificationChannel.EMAIL, title="Notice", body="Text", idempotency_key="notice-1")
    assert first.id == second.id
    with patch("apps.notifications.tasks.email_provider.send", return_value={"status": "sent"}) as send:
        deliver_notification(str(first.id))
        deliver_notification(str(first.id))
        assert send.call_count == 1
    for index in range(30):
        Notification.objects.create(recipient=owner, category=NotificationCategory.ADMIN_ALERT, channel=NotificationChannel.IN_APP, title=f"Alert {index}", body="Open")
    foreign = Notification.objects.create(recipient=other, category=NotificationCategory.EVENT, channel=NotificationChannel.IN_APP, title="Other", body="Private")
    api_client.force_authenticate(user=owner)
    assert api_client.get("/api/v1/notifications/unread-count/").data["data"]["count"] == 31
    assert api_client.post(f"/api/v1/notifications/{foreign.id}/mark-read/").status_code == 404
    assert api_client.post(f"/api/v1/notifications/{first.id}/mark-read/").status_code == 200
    assert api_client.get("/api/v1/notifications/unread-count/").data["data"]["count"] == 30


@pytest.mark.django_db
def test_quiet_hours_defer_external_delivery(accounts):
    owner, _, member = accounts
    now = timezone.now().astimezone(timezone.get_fixed_timezone(0))
    preference = CommunicationPreference.objects.create(
        user=owner, member=member, quiet_hours_enabled=True,
        quiet_hours_start=(now - timedelta(hours=1)).time().replace(tzinfo=None),
        quiet_hours_end=(now + timedelta(hours=1)).time().replace(tzinfo=None),
        timezone_name="UTC",
    )
    notification = queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.EMAIL, title="Quiet event", body="Later")
    assert notification.scheduled_for and notification.scheduled_for > timezone.now()
    with patch("apps.notifications.tasks.email_provider.send") as send:
        assert deliver_notification(str(notification.id))["status"] == "deferred"
        send.assert_not_called()
    preference.quiet_hours_enabled = False
    preference.save()
    notification.scheduled_for = None
    notification.save(update_fields=["scheduled_for"])
    with patch("apps.notifications.tasks.email_provider.send", return_value={"status": "sent"}) as send:
        deliver_notification(str(notification.id))
        send.assert_called_once()


@pytest.mark.django_db
def test_provider_failure_is_recorded_and_retry_succeeds(accounts):
    owner, _, _ = accounts
    notification = queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.EMAIL, title="Event", body="Soon")
    with patch("apps.notifications.tasks.email_provider.send", side_effect=RuntimeError("provider offline")):
        with pytest.raises(Exception):
            deliver_notification(str(notification.id))
    notification.refresh_from_db()
    assert notification.status == NotificationStatus.FAILED
    with patch("apps.notifications.tasks.email_provider.send", return_value={"status": "sent"}):
        deliver_notification(str(notification.id))
    notification.refresh_from_db()
    assert notification.status == NotificationStatus.SENT
    assert notification.attempts == 2


@pytest.mark.django_db
def test_unknown_provider_response_is_not_marked_sent(accounts):
    owner, _, _ = accounts
    notification = queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.EMAIL, title="Event", body="Soon")
    with patch("apps.notifications.tasks.email_provider.send", return_value={"status": "queued"}):
        with pytest.raises(Exception):
            deliver_notification(str(notification.id))
    notification.refresh_from_db()
    assert notification.status == NotificationStatus.FAILED
    assert notification.sent_at is None


@pytest.mark.django_db
def test_browser_push_requires_a_real_subscription(accounts):
    owner, _, _ = accounts
    assert queue_notification(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.PUSH, title="Event", body="Soon") is None
    legacy = Notification.objects.create(recipient=owner, category=NotificationCategory.EVENT, channel=NotificationChannel.PUSH, title="Old push", body="Soon")
    with patch("apps.notifications.providers.push_provider.send") as send:
        assert deliver_notification(str(legacy.id))["status"] == "stubbed"
        send.assert_not_called()


@pytest.mark.django_db
def test_public_prayer_requires_separate_opt_in(accounts):
    owner, _, member = accounts
    preference = CommunicationPreference.objects.create(user=owner, member=member, prayer_updates_enabled=True, prayer_notifications_enabled=False)
    assert queue_notification(recipient=owner, category=NotificationCategory.PUBLIC_PRAYER, channel=NotificationChannel.EMAIL, title="Prayer", body="Shared") is None
    preference.prayer_notifications_enabled = True
    preference.save()
    assert queue_notification(recipient=owner, category=NotificationCategory.PUBLIC_PRAYER, channel=NotificationChannel.EMAIL, title="Prayer", body="Shared") is not None


@pytest.mark.django_db
def test_live_service_fanout_respects_branch_and_opt_out(accounts, make_user, branch_a):
    from apps.notifications.live import notify_live_service_published
    from apps.operations.models import ContentEntry, ContentStatus, ContentType

    owner, other_branch, member = accounts
    opted_in = make_user(email="live-in@chapelflow.test", branch=branch_a)
    CommunicationPreference.objects.create(user=owner, member=member, live_service_enabled=False)
    entry = ContentEntry.objects.create(
        branch=branch_a, content_type=ContentType.LIVESTREAM,
        title="Sunday chapel", slug="sunday-chapel-live", details="Join us",
        status=ContentStatus.PUBLISHED, published_at=timezone.now(),
    )
    assert notify_live_service_published(str(entry.id))["created"] == 1
    assert notify_live_service_published(str(entry.id))["created"] == 0
    notifications = Notification.objects.filter(category=NotificationCategory.LIVE_SERVICE)
    assert list(notifications.values_list("recipient_id", flat=True)) == [opted_in.id]
    assert notifications.get().href == "/livestream"
    assert not notifications.filter(recipient=other_branch).exists()
