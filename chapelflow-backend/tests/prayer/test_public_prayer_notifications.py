import pytest


@pytest.mark.django_db
<<<<<<< HEAD
def test_prayer_notifications_are_opt_in_and_idempotent(api_client, member_in_branch_a, branch_a, mocker, django_capture_on_commit_callbacks):
=======
def test_prayer_notifications_are_opt_in_and_idempotent(api_client, member_in_branch_a, branch_a, mocker):
>>>>>>> origin/main
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
<<<<<<< HEAD
        consent_to_share=True,
    )
    deliver = mocker.patch("apps.prayer.notifications.deliver_notification.delay")

    with django_capture_on_commit_callbacks(execute=True):
        first = broadcast_public_prayer_notifications(str(request.id))
        second = broadcast_public_prayer_notifications(str(request.id))
=======
    )
    deliver = mocker.patch("apps.prayer.notifications.deliver_notification.delay")

    first = broadcast_public_prayer_notifications(str(request.id))
    second = broadcast_public_prayer_notifications(str(request.id))
>>>>>>> origin/main

    notices = Notification.objects.filter(source_prayer_request=request)
    assert first["notifications_created"] == 1
    assert second["notifications_created"] == 1
    assert notices.count() == 1
    assert "Private health detail" not in notices.get().body
    assert deliver.call_count == 1
<<<<<<< HEAD


@pytest.mark.django_db
def test_unconsented_public_prayer_is_private_in_assignment_notification(member_in_branch_a, branch_a, mocker):
    from apps.notifications.models import Notification
    from apps.prayer.models import PrayerPrivacyLevel, PrayerRequest, PrayerCategory
    from apps.prayer.notifications import notify_prayer_request_assigned

    member_in_branch_a.user.email = "pastoral-recipient@example.edu"
    member_in_branch_a.user.save(update_fields=["email"])
    request = PrayerRequest.objects.create(
        branch=branch_a,
        submitted_by_name="Anonymous requester",
        category=PrayerCategory.HEALING,
        details="Sensitive medical information",
        privacy_level=PrayerPrivacyLevel.PUBLIC,
        consent_to_share=False,
    )
    mocker.patch("apps.prayer.notifications.deliver_notification.delay")

    notify_prayer_request_assigned(request, member_in_branch_a.user)

    notification = Notification.objects.get(recipient=member_in_branch_a.user)
    assert "Sensitive medical information" not in notification.body
    assert "Anonymous requester" not in notification.body
    assert "HEALING" not in notification.body
=======
>>>>>>> origin/main
