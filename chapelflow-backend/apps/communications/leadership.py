"""Scoped, private leadership channel and read-only community oversight."""
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log
from apps.groups.models import GroupJoinRequest, GroupMeeting, GroupMembership, GroupMessage, GroupResource, GroupRole, JoinRequestStatus
from apps.ministries.models import Group
from apps.notifications.models import Notification, NotificationCategory, NotificationChannel
from apps.notifications.preferences import queue_notification
from common.utils.responses import error_response, success_response

from .models import LeadershipDelivery, LeadershipNotice, LeadershipReply

SENDER_ROLES = {"SUPER_ADMIN", "CHAPLAIN", "STUDENT_CHAPLAIN"}
LEADER_ROLES = {"UNIT_HEAD", "FELLOWSHIP_LEADER"}
GROUP_TYPES = {"UNIT", "FELLOWSHIP"}


def _role(user):
    return user.get_role_code()


def _groups(user):
    """Staff oversight never creates group membership or inherits leader write access."""
    groups = Group.objects.filter(is_active=True, group_type__in=GROUP_TYPES)
    role = _role(user)
    if role not in SENDER_ROLES or not user.is_active:
        return groups.none()
    if role == "SUPER_ADMIN":
        return groups
    if not user.branch_id:
        return groups.none()
    if role == "CHAPLAIN":
        return groups.filter(branch__organization_id=user.branch.organization_id)
    return groups.filter(branch_id=user.branch_id)


def _notice_scope(user):
    notices = LeadershipNotice.objects.all()
    if _role(user) == "SUPER_ADMIN" and user.is_active:
        return notices
    if not user.is_active or not user.branch_id:
        return notices.none()
    if _role(user) == "CHAPLAIN":
        return notices.filter(branch__organization_id=user.branch.organization_id)
    if _role(user) == "STUDENT_CHAPLAIN":
        return notices.filter(branch_id=user.branch_id)
    return notices.none()


def _notice_data(notice, delivery=None):
    return {
        "id": str(notice.id), "title": notice.title, "body": notice.body,
        "audience": notice.audience, "branch_id": str(notice.branch_id),
        "branch_name": notice.branch.name, "sender": (notice.created_by.full_name or notice.created_by.email) if notice.created_by else "Former chaplain",
        "created_at": notice.created_at,
        "target_group_ids": [str(group_id) for group_id in notice.target_groups.values_list("id", flat=True)],
        "recipient_count": notice.deliveries.count(),
        "read_at": delivery.read_at if delivery else None,
        "acknowledged_at": delivery.acknowledged_at if delivery else None,
    }


class CommunityOversightView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id=None):
        groups = _groups(request.user).select_related("branch").order_by("branch__name", "group_type", "name")
        if group_id is None:
            rows = []
            for group in groups:
                rows.append({
                    "id": str(group.id), "name": group.name, "type": group.group_type,
                    "branch_id": str(group.branch_id), "branch_name": group.branch.name,
                    "member_count": GroupMembership.objects.filter(group=group, is_active=True).count(),
                    "pending_count": GroupJoinRequest.objects.filter(group=group, status=JoinRequestStatus.PENDING).count(),
                    "latest_activity": GroupMessage.objects.filter(group=group).order_by("-created_at").values_list("created_at", flat=True).first(),
                })
            return success_response(rows)
        group = groups.filter(id=group_id).first()
        if group is None:
            return error_response("Community not found.", status=404)
        from apps.communications.models import Announcement, AnnouncementStatus
        from apps.moderation.models import TargetKind
        from apps.moderation.services import visible

        messages = visible(GroupMessage.objects.filter(group=group), TargetKind.GROUP_MESSAGE).select_related("author").order_by("-created_at")[:100]
        resources = visible(GroupResource.objects.filter(group=group), TargetKind.GROUP_RESOURCE).order_by("-created_at")[:50]
        announcements = visible(Announcement.objects.filter(
            branch=group.branch, target_groups=group,
            status__in=[AnnouncementStatus.QUEUED, AnnouncementStatus.SENDING, AnnouncementStatus.COMPLETED],
        ), TargetKind.GROUP_ANNOUNCEMENT).order_by("-publish_at")[:50]
        write_audit_log(AuditAction.COMMUNICATION_ACTION, "community_oversight", group.id, user=request.user, metadata={"verb": "view", "branch_id": str(group.branch_id)})
        return success_response({
            "id": str(group.id), "name": group.name, "type": group.group_type,
            "branch_name": group.branch.name,
            "member_count": GroupMembership.objects.filter(group=group, is_active=True).count(),
            "pending_count": GroupJoinRequest.objects.filter(group=group, status=JoinRequestStatus.PENDING).count(),
            "pending_requests": [{"id": str(row.id), "name": row.member.full_name, "requested_at": row.requested_at} for row in GroupJoinRequest.objects.filter(group=group, status=JoinRequestStatus.PENDING).select_related("member").order_by("-requested_at")[:50]],
            "messages": [{"id": str(row.id), "body": row.body, "author": row.author.full_name or row.author.email, "created_at": row.created_at} for row in messages],
            "announcements": [{"id": str(row.id), "title": row.title, "body": row.body, "published_at": row.publish_at} for row in announcements],
            "meetings": [{"id": str(row.id), "title": row.title, "starts_at": row.starts_at, "location": row.location} for row in GroupMeeting.objects.filter(group=group).order_by("-starts_at")[:50]],
            "resources": [{"id": str(row.id), "title": row.title, "url": row.url} for row in resources],
        })


def _recipients(groups):
    """Snapshot active assigned accounts and active membership leaders, with no duplicates."""
    ids = set()
    for group in groups:
        role = "UNIT_HEAD" if group.group_type == "UNIT" else "FELLOWSHIP_LEADER"
        ids.update(User.objects.filter(
            is_active=True, institutional_group=group, branch=group.branch, role=role,
        ).values_list("id", flat=True))
    ids.update(GroupMembership.objects.filter(
        group__in=groups, is_active=True, member__user__is_active=True,
        role__in=[GroupRole.LEADER, GroupRole.ASSISTANT_LEADER],
    ).values_list("member__user_id", flat=True))
    return User.objects.filter(id__in=ids, is_active=True).order_by("id")


class LeadershipNoticeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_active:
            return error_response("Account inactive.", status=403)
        view = request.query_params.get("view", "inbox")
        if view == "sent":
            if _role(request.user) not in SENDER_ROLES:
                return error_response("Not authorized.", status=403)
            notices = _notice_scope(request.user).filter(created_by=request.user).select_related("branch", "created_by").order_by("-created_at")[:100]
            return success_response([_notice_data(row) for row in notices])
        deliveries = LeadershipDelivery.objects.filter(recipient=request.user).select_related("notice", "notice__branch", "notice__created_by").order_by("-notice__created_at")[:100]
        return success_response([_notice_data(row.notice, row) for row in deliveries])

    def post(self, request):
        if _role(request.user) not in SENDER_ROLES or not request.user.is_active:
            return error_response("Not authorized.", status=403)
        title = str(request.data.get("title", "")).strip()
        body = str(request.data.get("body", "")).strip()
        audience = str(request.data.get("audience", "")).upper()
        branch_id = str(request.data.get("branch_id", request.user.branch_id or ""))
        if not title or not body or len(title) > 180 or len(body) > 5000:
            return error_response("A title (up to 180 characters) and message (up to 5,000 characters) are required.", status=400)
        if audience not in {"ALL", "UNIT", "FELLOWSHIP", "SELECTED"}:
            return error_response("Choose a valid leadership audience.", status=400)
        scoped = _groups(request.user).filter(branch_id=branch_id)
        if not scoped.exists():
            return error_response("Branch not available.", status=403)
        selected = request.data.get("target_group_ids", [])
        if audience == "SELECTED":
            if not isinstance(selected, list) or not selected or len(selected) > 100:
                return error_response("Select one or more communities.", status=400)
            try:
                selected_ids = {str(uuid.UUID(str(item))) for item in selected}
            except (ValueError, TypeError, AttributeError):
                return error_response("Invalid community identifier.", status=400)
            groups = list(scoped.filter(id__in=selected_ids))
            if len(groups) != len(selected_ids):
                return error_response("A selected community is outside your scope.", status=403)
        else:
            groups = list(scoped.filter(group_type=audience)) if audience != "ALL" else list(scoped)
        if not groups:
            return error_response("No active communities match this audience.", status=400)
        recipients = list(_recipients(groups))
        if not recipients:
            return error_response("No active leaders are assigned to these communities.", status=400)
        email_requested = request.data.get("email_requested") is True
        with transaction.atomic():
            notice = LeadershipNotice.objects.create(
                branch_id=branch_id, created_by=request.user, title=title, body=body,
                audience=audience, email_requested=email_requested,
            )
            notice.target_groups.set(groups)
            LeadershipDelivery.objects.bulk_create([
                LeadershipDelivery(notice=notice, recipient=recipient) for recipient in recipients
            ])
            for recipient in recipients:
                base = dict(recipient=recipient, category=NotificationCategory.ADMIN_ALERT, title=title,
                            body=body, href=f"/app/leadership-notices/{notice.id}")
                queue_notification(channel=NotificationChannel.IN_APP, idempotency_key=f"leadership:{notice.id}:{recipient.id}:in-app", **base)
                if email_requested:
                    queue_notification(channel=NotificationChannel.EMAIL, idempotency_key=f"leadership:{notice.id}:{recipient.id}:email", **base)
            write_audit_log(AuditAction.COMMUNICATION_ACTION, "leadership_notice", notice.id, user=request.user,
                            metadata={"verb": "send", "branch_id": branch_id, "audience": audience, "recipient_count": len(recipients)})
        return success_response(_notice_data(notice), status=201)


class LeadershipNoticeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _access(self, request, notice_id):
        delivery = LeadershipDelivery.objects.filter(notice_id=notice_id, recipient=request.user).select_related("notice", "notice__branch", "notice__created_by").first()
        if delivery and request.user.is_active and request.user.id in set(_recipients(list(delivery.notice.target_groups.all())).values_list("id", flat=True)):
            return delivery.notice, delivery, True
        notice = _notice_scope(request.user).filter(id=notice_id, created_by=request.user).select_related("branch", "created_by").first() if _role(request.user) in SENDER_ROLES else None
        return notice, None, False

    def get(self, request, notice_id):
        notice, delivery, is_recipient = self._access(request, notice_id)
        if notice is None:
            return error_response("Notice not found.", status=404)
        if is_recipient and delivery.read_at is None:
            delivery.read_at = timezone.now()
            delivery.save(update_fields=["read_at"])
        rows = list(notice.deliveries.select_related("recipient").prefetch_related("replies__author").order_by("recipient__first_name", "recipient__last_name"))
        if is_recipient:
            rows = [delivery]
        keys = [f"leadership:{notice.id}:{row.recipient_id}:in-app" for row in rows]
        states = {row.idempotency_key: row.status for row in Notification.objects.filter(idempotency_key__in=keys)}
        write_audit_log(AuditAction.COMMUNICATION_ACTION, "leadership_notice", notice.id, user=request.user, metadata={"verb": "view"})
        return success_response({
            **_notice_data(notice, delivery),
            "deliveries": [{
                "id": str(row.id), "recipient_name": row.recipient.full_name or row.recipient.email,
                "read_at": row.read_at, "acknowledged_at": row.acknowledged_at,
                "delivery_status": states.get(f"leadership:{notice.id}:{row.recipient_id}:in-app", "SKIPPED"),
                "replies": [{"id": str(reply.id), "author": reply.author.full_name or reply.author.email, "body": reply.body, "created_at": reply.created_at} for reply in row.replies.all()],
            } for row in rows],
        })

    def post(self, request, notice_id):
        notice, delivery, is_recipient = self._access(request, notice_id)
        if notice is None or not is_recipient:
            return error_response("Notice not found.", status=404)
        if delivery.acknowledged_at is None:
            delivery.acknowledged_at = timezone.now()
            delivery.read_at = delivery.read_at or delivery.acknowledged_at
            delivery.save(update_fields=["read_at", "acknowledged_at"])
            write_audit_log(AuditAction.COMMUNICATION_ACTION, "leadership_notice", notice.id, user=request.user, metadata={"verb": "acknowledge"})
        return success_response({"acknowledged_at": delivery.acknowledged_at})


class LeadershipReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notice_id):
        if not request.user.is_active:
            return error_response("Account inactive.", status=403)
        body = str(request.data.get("body", "")).strip()
        if not body or len(body) > 2000:
            return error_response("A reply of up to 2,000 characters is required.", status=400)
        delivery = LeadershipDelivery.objects.filter(
            notice_id=notice_id, recipient=request.user,
        ).select_related("notice").first()
        if delivery is not None and request.user.id not in set(_recipients(list(delivery.notice.target_groups.all())).values_list("id", flat=True)):
            delivery = None
        if delivery is None and _role(request.user) in SENDER_ROLES:
            notice = _notice_scope(request.user).filter(id=notice_id, created_by=request.user).first()
            try:
                delivery_id = uuid.UUID(str(request.data.get("delivery_id")))
            except (ValueError, TypeError, AttributeError):
                return error_response("Choose a recipient thread.", status=400)
            delivery = LeadershipDelivery.objects.filter(notice=notice, id=delivery_id).first() if notice else None
        if delivery is None:
            return error_response("Notice not found.", status=404)
        reply = LeadershipReply.objects.create(delivery=delivery, author=request.user, body=body)
        other = delivery.notice.created_by if request.user.id == delivery.recipient_id else delivery.recipient
        if other:
            queue_notification(recipient=other, category=NotificationCategory.ADMIN_ALERT,
                           channel=NotificationChannel.IN_APP, title=f"Reply: {delivery.notice.title}",
                           body=body, href=f"/app/leadership-notices/{notice_id}",
                           idempotency_key=f"leadership-reply:{reply.id}:{other.id}")
        write_audit_log(AuditAction.COMMUNICATION_ACTION, "leadership_reply", reply.id, user=request.user, metadata={"notice_id": str(notice_id)})
        return success_response({"id": str(reply.id), "body": reply.body, "created_at": reply.created_at}, status=201)
