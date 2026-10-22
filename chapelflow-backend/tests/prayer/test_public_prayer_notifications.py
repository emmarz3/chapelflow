import pytest


@pytest.mark.django_db
def test_prayer_notifications_are_opt_in_and_idempotent(api_client, member_in_branch_a, branch_a, mocker):
    from apps.communications.models import CommunicationPreference
    from apps.notifications.models import Notification
    from apps.prayer.models import PrayerPrivacyLevel, PrayerRequest, PrayerCategory
    from apps.prayer.notifications import broadcast_public_prayer_notifications

    member_in_branch_a.user.email = "prayer-recipient@example.edu"
    member_in_branch_a.user.save(update_fields=["email"])
    api_client.force_authenticate(user=member_in_branch_a.user)
    response = api_client.get("/api/v1/communications/preferences/me/")
    assert response.status_code == 200
    assert response.data["data"]["prayer_notifications_enabled"] is False

    response = api_client.patch(
        "/api/v1/communications/preferences/me/",
        {"prayer_notifications_enabled": True},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["data"]["prayer_notifications_enabled"] is True

    preference, _ = CommunicationPreference.objects.get_or_create(member=member_in_branch_a)
    preference.email_enabled = True
    preference.prayer_notifications_enabled = True
    preference.save()
    request = PrayerRequest.objects.create(
        branch=branch_a,
        member=member_in_branch_a,
        category=PrayerCategory.OTHER,
        details="Private health detail must not be emailed.",
        privacy_level=PrayerPrivacyLevel.PUBLIC,
    )
    deliver = mocker.patch("apps.prayer.notifications.deliver_notification.delay")

    first = broadcast_public_prayer_notifications(str(request.id))
    second = broadcast_public_prayer_notifications(str(request.id))

    notices = Notification.objects.filter(source_prayer_request=request)
    assert first["notifications_created"] == 1
    assert second["notifications_created"] == 1
    assert notices.count() == 1
    assert "Private health detail" not in notices.get().body
    assert deliver.call_count == 1
