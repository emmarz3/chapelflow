import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(WEB_PUSH_PUBLIC_KEY="public", WEB_PUSH_PRIVATE_KEY="private")
def test_web_push_requires_auth_and_trusted_endpoint(api_client, make_user):
    path = "/api/v1/notifications/push-subscription/"
    payload = {"endpoint": "https://fcm.googleapis.com/fcm/send/one", "keys": {"p256dh": "a" * 32, "auth": "b" * 16}}
    assert api_client.post(path, payload, format="json").status_code == 401
    member = make_user(email="push@chapelflow.test")
    api_client.force_authenticate(user=member)
    assert api_client.post(path, {**payload, "endpoint": "https://localhost/private"}, format="json").status_code == 400
    assert api_client.post(path, payload, format="json").status_code == 200
    from apps.notifications.models import Notification, NotificationChannel, WebPushSubscription
    assert WebPushSubscription.objects.filter(user=member).count() == 1
    Notification.objects.create(recipient=member, channel=NotificationChannel.PUSH, title="Push", body="Hidden from inbox")
    assert api_client.get("/api/v1/notifications/unread-count/").data["data"]["count"] == 0
    assert api_client.delete(path + "?endpoint=https%3A%2F%2Ffcm.googleapis.com%2Ffcm%2Fsend%2Fone").status_code == 200
    assert not WebPushSubscription.objects.filter(user=member).exists()
