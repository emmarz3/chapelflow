import pytest
from django.test import override_settings

from apps.moderation.models import ModerationEvent, ModerationReport, ModerationRestriction
from apps.audit.models import AuditLog
from apps.notifications.models import Notification
from apps.social.models import SocialComment, SocialPost
from common.constants.roles import Roles


@pytest.fixture
def people(make_user, branch_a, branch_b):
    reporter = make_user(email="reporter@chapelflow.test", branch=branch_a)
    author = make_user(email="author@chapelflow.test", branch=branch_a)
    outsider = make_user(email="outsider@chapelflow.test", branch=branch_b)
    moderator = make_user(email="moderator@chapelflow.test", branch=branch_a, role=Roles.CHAPEL_ADMIN, mfa_enabled=True)
    other_moderator = make_user(email="othermoderator@chapelflow.test", branch=branch_b, role=Roles.CHAPEL_ADMIN, mfa_enabled=True)
    post = SocialPost.objects.create(branch=branch_a, author=author, caption="A shared moment")
    return reporter, author, outsider, moderator, other_moderator, post


@pytest.mark.django_db
def test_report_is_stored_and_reporter_sees_only_own_status(api_client, people):
    reporter, author, outsider, moderator, _, post = people
    api_client.force_authenticate(user=reporter)
    response = api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "HARASSMENT", "explanation": "Harmful caption"}, format="json")
    assert response.status_code == 201
    report = ModerationReport.objects.get(pk=response.data["data"]["id"])
    assert (report.reporter, report.branch_id, report.reason, report.content_snapshot) == (reporter, post.branch_id, "HARASSMENT", post.caption)
    assert ModerationEvent.objects.filter(report=report, action="REPORT").exists()
    assert "reporter_id" not in response.data["data"]
    assert "events" not in api_client.get("/api/v1/moderation/reports/").data["data"][0]
    api_client.force_authenticate(user=author)
    assert api_client.get("/api/v1/moderation/reports/").data["data"] == []
    assert api_client.get(f"/api/v1/moderation/queue/{report.id}/").status_code == 403
    api_client.force_authenticate(user=outsider)
    assert api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "SPAM"}, format="json").status_code == 404


@pytest.mark.django_db
def test_moderator_scope_and_audited_visibility_actions(api_client, people):
    reporter, _, _, moderator, other_moderator, post = people
    api_client.force_authenticate(user=reporter)
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "PRIVACY"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=other_moderator)
    assert api_client.get("/api/v1/moderation/queue/").data["data"] == []
    assert api_client.get(f"/api/v1/moderation/queue/{report_id}/").status_code == 404
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "HIDE", "note": "Review"}, format="json").status_code == 404
    api_client.force_authenticate(user=moderator)
    assert len(api_client.get("/api/v1/moderation/queue/").data["data"]) == 1
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "HIDE", "note": "Contains private information"}, format="json").status_code == 200
    assert ModerationRestriction.objects.filter(target_id=post.id, state="HIDDEN").exists()
    assert Notification.objects.filter(recipient=reporter, title="Community report updated").exists()
    api_client.force_authenticate(user=reporter)
    assert api_client.get("/api/v1/social/posts/").data["data"]["items"] == []
    assert api_client.get("/api/v1/moderation/reports/").data["data"][0]["status"] == "REVIEWED"
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "RESTORE"}, format="json").status_code == 200
    assert not ModerationRestriction.objects.filter(target_id=post.id).exists()
    assert list(ModerationEvent.objects.filter(report_id=report_id).values_list("action", flat=True)) == ["REPORT", "HIDE", "RESTORE"]
    assert AuditLog.objects.filter(resource_type="ModerationReport", resource_id=report_id).count() == 3
    api_client.force_authenticate(user=reporter)
    assert len(api_client.get("/api/v1/social/posts/").data["data"]["items"]) == 1


@pytest.mark.django_db
def test_comment_report_and_removed_comment_are_inaccessible(api_client, people):
    reporter, author, _, moderator, _, post = people
    comment = SocialComment.objects.create(post=post, author=author, body="A harmful reply")
    api_client.force_authenticate(user=reporter)
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "COMMENT", "target_id": str(comment.id), "reason": "BULLYING"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "REMOVE", "note": "Bullying"}, format="json").status_code == 200
    api_client.force_authenticate(user=reporter)
    assert api_client.get(f"/api/v1/social/posts/{post.id}/comments/").data["data"] == []
    assert api_client.get("/api/v1/social/posts/").data["data"]["items"][0]["comment_count"] == 0


@pytest.mark.django_db
def test_duplicate_and_invalid_reports_are_rejected(api_client, people):
    reporter, _, _, _, _, post = people
    api_client.force_authenticate(user=reporter)
    payload = {"target_kind": "POST", "target_id": str(post.id), "reason": "SPAM"}
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 201
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 400
    assert api_client.post("/api/v1/moderation/reports/", {**payload, "reason": "NOT_A_REASON"}, format="json").status_code == 400


@pytest.mark.django_db
@override_settings(MFA_ENFORCED_ROLES=[Roles.CHAPEL_ADMIN], MFA_ENFORCE_ROLE_OBJECTS=False)
def test_non_super_admin_cannot_suspend_and_mfa_is_required(api_client, people):
    reporter, _, _, moderator, _, post = people
    api_client.force_authenticate(user=reporter)
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "IMPERSONATION"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "SUSPEND", "note": "Impersonation"}, format="json").status_code == 403
    moderator.mfa_enabled = False
    moderator.save(update_fields=["mfa_enabled"])
    assert api_client.get("/api/v1/moderation/queue/").status_code == 403


@pytest.mark.django_db
def test_group_message_report_requires_membership_and_hides_message(api_client, people, branch_a):
    from apps.groups.models import GroupMembership, GroupMessage
    from apps.members.models import Member
    from apps.ministries.models import Group

    reporter, author, outsider, moderator, _, _ = people
    group = Group.objects.create(branch=branch_a, name="Fellowship", group_type="FELLOWSHIP")
    member = Member.objects.create(branch=branch_a, user=reporter, first_name="Report", last_name="Member")
    GroupMembership.objects.create(group=group, member=member)
    message = GroupMessage.objects.create(group=group, author=author, body="An abusive group message")
    payload = {"target_kind": "GROUP_MESSAGE", "target_id": str(message.id), "reason": "HARASSMENT"}
    api_client.force_authenticate(user=outsider)
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 404
    api_client.force_authenticate(user=reporter)
    assert len(api_client.get(f"/api/v1/community-memberships/{group.id}/messages/").data["data"]) == 1
    report_id = api_client.post("/api/v1/moderation/reports/", payload, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "HIDE", "note": "Confirmed"}, format="json").status_code == 200
    api_client.force_authenticate(user=reporter)
    assert api_client.get(f"/api/v1/community-memberships/{group.id}/messages/").data["data"] == []


@pytest.mark.django_db
def test_private_prayer_cannot_be_reported_by_another_member(api_client, people, branch_a):
    from apps.members.models import Member
    from apps.prayer.models import PrayerRequest

    reporter, author, _, _, _, _ = people
    member = Member.objects.create(branch=branch_a, user=author, first_name="Prayer", last_name="Member")
    prayer = PrayerRequest.objects.create(branch=branch_a, member=member, details="Confidential request", privacy_level="PRIVATE", is_private=True)
    api_client.force_authenticate(user=reporter)
    assert api_client.post("/api/v1/moderation/reports/", {"target_kind": "PRAYER", "target_id": str(prayer.id), "reason": "PRIVACY"}, format="json").status_code == 404
    api_client.force_authenticate(user=author)
    assert api_client.post("/api/v1/moderation/reports/", {"target_kind": "PRAYER", "target_id": str(prayer.id), "reason": "PRIVACY"}, format="json").status_code == 201


@pytest.mark.django_db
def test_report_rate_limit_rejects_sixth_report(api_client, people, branch_a):
    reporter, author, _, _, _, _ = people
    api_client.force_authenticate(user=reporter)
    responses = []
    for index in range(6):
        post = SocialPost.objects.create(branch=branch_a, author=author, caption=f"Post {index}")
        responses.append(api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "SPAM"}, format="json").status_code)
    assert responses == [201, 201, 201, 201, 201, 429]


@pytest.mark.django_db
def test_fake_image_upload_is_rejected_before_publication(api_client, people):
    from django.core.files.uploadedfile import SimpleUploadedFile

    reporter, _, _, _, _, _ = people
    api_client.force_authenticate(user=reporter)
    fake = SimpleUploadedFile("photo.png", b"<script>alert('unsafe')</script>", content_type="image/png")
    response = api_client.post("/api/v1/social/posts/", {"caption": "Photo", "files": fake}, format="multipart")
    assert response.status_code == 400
    assert not SocialPost.objects.filter(caption="Photo").exists()


@pytest.mark.django_db
def test_reported_group_link_is_hidden_from_library(api_client, people, branch_a):
    from apps.groups.models import GroupMembership, GroupResource
    from apps.members.models import Member
    from apps.ministries.models import Group

    reporter, author, _, moderator, _, _ = people
    group = Group.objects.create(branch=branch_a, name="Study", group_type="FELLOWSHIP")
    member = Member.objects.create(branch=branch_a, user=reporter, first_name="Study", last_name="Member")
    GroupMembership.objects.create(group=group, member=member)
    resource = GroupResource.objects.create(group=group, title="External link", url="https://example.org/study", created_by=author)
    api_client.force_authenticate(user=reporter)
    assert len(api_client.get(f"/api/v1/community-memberships/{group.id}/resources/").data["data"]) == 1
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "GROUP_RESOURCE", "target_id": str(resource.id), "reason": "SPAM"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "HIDE", "note": "Unsafe link"}, format="json").status_code == 200
    api_client.force_authenticate(user=reporter)
    assert api_client.get(f"/api/v1/community-memberships/{group.id}/resources/").data["data"] == []


@pytest.mark.django_db
def test_post_rate_limit_and_duplicate_content(api_client, people):
    reporter, _, _, _, _, _ = people
    api_client.force_authenticate(user=reporter)
    first = api_client.post("/api/v1/social/posts/", {"caption": "Same post"}, format="multipart")
    duplicate = api_client.post("/api/v1/social/posts/", {"caption": "Same post"}, format="multipart")
    statuses = [api_client.post("/api/v1/social/posts/", {"caption": f"Post {index}"}, format="multipart").status_code for index in range(9)]
    assert first.status_code == 201
    assert duplicate.status_code == 400
    assert statuses == [201] * 8 + [429]


@pytest.mark.django_db
def test_reported_moderator_cannot_see_reporter_identity_or_review_own_content(api_client, people, branch_a):
    reporter, _, _, moderator, _, _ = people
    post = SocialPost.objects.create(branch=branch_a, author=moderator, caption="Moderator's post")
    api_client.force_authenticate(user=reporter)
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "HARASSMENT"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.get("/api/v1/moderation/queue/").data["data"] == []
    assert api_client.get(f"/api/v1/moderation/queue/{report_id}/").status_code == 404
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "DISMISS", "note": "Own post"}, format="json").status_code == 404


@pytest.mark.django_db
def test_super_admin_can_suspend_reported_author(api_client, people, make_user, branch_a):
    reporter, author, _, _, _, post = people
    super_admin = make_user(email="superadmin@chapelflow.test", branch=branch_a, role=Roles.SUPER_ADMIN, mfa_enabled=True)
    api_client.force_authenticate(user=reporter)
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "POST", "target_id": str(post.id), "reason": "IMPERSONATION"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=super_admin)
    response = api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "SUSPEND", "note": "Confirmed impersonation"}, format="json")
    assert response.status_code == 200
    author.refresh_from_db()
    assert not author.is_active
    assert ModerationRestriction.objects.filter(target_id=post.id, state="HIDDEN").exists()
    assert ModerationEvent.objects.filter(report_id=report_id, action="SUSPEND", actor=super_admin).exists()


@pytest.mark.django_db
def test_group_announcement_report_hides_both_member_feeds(api_client, people, branch_a):
    from django.utils import timezone
    from apps.communications.models import Announcement, AnnouncementStatus
    from apps.groups.models import GroupMembership
    from apps.members.models import Member
    from apps.ministries.models import Group

    reporter, author, _, moderator, _, _ = people
    group = Group.objects.create(branch=branch_a, name="Fellowship news", group_type="FELLOWSHIP")
    member = Member.objects.create(branch=branch_a, user=reporter, first_name="News", last_name="Member")
    GroupMembership.objects.create(group=group, member=member)
    announcement = Announcement.objects.create(
        branch=branch_a, title="Group notice", body="A harmful notice", status=AnnouncementStatus.COMPLETED,
        created_by=author, publish_at=timezone.now(),
    )
    announcement.target_groups.add(group)
    api_client.force_authenticate(user=reporter)
    assert len(api_client.get(f"/api/v1/community-memberships/{group.id}/announcements/").data["data"]) == 1
    report_id = api_client.post("/api/v1/moderation/reports/", {"target_kind": "GROUP_ANNOUNCEMENT", "target_id": str(announcement.id), "reason": "HATE_SPEECH"}, format="json").data["data"]["id"]
    api_client.force_authenticate(user=moderator)
    assert api_client.post(f"/api/v1/moderation/queue/{report_id}/", {"action": "HIDE", "note": "Harmful content"}, format="json").status_code == 200
    api_client.force_authenticate(user=reporter)
    assert api_client.get(f"/api/v1/community-memberships/{group.id}/announcements/").data["data"] == []
    assert api_client.get("/api/v1/communications/announcements/me/").data["data"] == []


@pytest.mark.django_db
def test_testimony_report_is_limited_to_owner_and_pastoral_moderator(api_client, people, branch_a):
    from apps.members.models import Member
    from apps.prayer.models import Testimony

    reporter, author, outsider, moderator, _, _ = people
    member = Member.objects.create(branch=branch_a, user=author, first_name="Story", last_name="Owner")
    testimony = Testimony.objects.create(branch=branch_a, member=member, title="A story", details="Private testimony")
    payload = {"target_kind": "TESTIMONY", "target_id": str(testimony.id), "reason": "PRIVACY"}
    api_client.force_authenticate(user=reporter)
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 404
    api_client.force_authenticate(user=outsider)
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 404
    api_client.force_authenticate(user=author)
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 201
    api_client.force_authenticate(user=moderator)
    assert api_client.post("/api/v1/moderation/reports/", payload, format="json").status_code == 201
