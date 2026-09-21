from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.members.tasks import bulk_import_members_task
from apps.notifications.models import Notification, NotificationStatus
from common.constants.roles import Roles


User = get_user_model()


@pytest.fixture
def requesting_user():
    return User.objects.create_user(
        email="member-import-admin@example.com",
        password="StrongPassword123!",
        role=Roles.SUPER_ADMIN,
    )


@pytest.mark.django_db
def test_successful_import_notifies_requesting_user(requesting_user):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"csv-content"
    summary = {
        "total": 4,
        "created": 2,
        "updated": 1,
        "failed": 1,
        "row_results": [],
    }

    with (
        patch("urllib.request.urlopen", return_value=response),
        patch("apps.members.services.parse_and_import_members", return_value=summary),
        patch("apps.notifications.tasks.deliver_notification.delay") as deliver,
    ):
        result = bulk_import_members_task("https://storage.example/import.csv", requesting_user.id)

    notification = Notification.objects.get(recipient=requesting_user)
    assert result == summary
    assert notification.title == "Member import completed"
    assert "Created: 2" in notification.body
    assert "Updated: 1" in notification.body
    assert "Failed: 1" in notification.body
    deliver.assert_called_once_with(str(notification.id))


@pytest.mark.django_db
def test_failed_import_notifies_requesting_user_and_reraises(requesting_user):
    with (
        patch("urllib.request.urlopen", side_effect=OSError("storage unavailable")),
        patch("apps.notifications.tasks.deliver_notification.delay") as deliver,
        pytest.raises(OSError, match="storage unavailable"),
    ):
        bulk_import_members_task("https://storage.example/import.csv", requesting_user.id)

    notification = Notification.objects.get(recipient=requesting_user)
    assert notification.title == "Member import failed"
    assert notification.status == NotificationStatus.PENDING
    assert "storage unavailable" not in notification.body
    deliver.assert_called_once_with(str(notification.id))
