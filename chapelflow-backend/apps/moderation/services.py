from django.db.models import Subquery
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.groups.models import GroupMessage, GroupResource
from apps.communications.models import Announcement, AnnouncementStatus
from apps.prayer.models import PrayerRequest, Testimony
from apps.social.models import SocialComment, SocialPost, SocialPostStatus, SocialCommentStatus
from common.constants.roles import Roles
from common.permissions.rbac import user_has_completed_required_mfa

from .models import ModerationRestriction, TargetKind


def can_moderate(user):
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    return bool(user.is_active and role in Roles.PASTORAL_ACCESS_ROLES and user_has_completed_required_mfa(user))


def scoped_reports(user):
    from .models import ModerationReport

    if not can_moderate(user):
        raise PermissionDenied("Only authorized pastoral moderators can review reports.")
    role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
    if role in Roles.GLOBAL_SCOPE_ROLES:
        reports = ModerationReport.objects.all()
    else:
        reports = ModerationReport.objects.filter(branch_id=user.branch_id) if user.branch_id else ModerationReport.objects.none()
    return reports.exclude(target_author=user).exclude(reporter=user)


def visible(queryset, kind):
    restricted = ModerationRestriction.objects.filter(target_kind=kind).values("target_id")
    return queryset.exclude(pk__in=Subquery(restricted))


def target_for_report(request, kind, target_id):
    user = request.user
    if kind == TargetKind.POST:
        target = SocialPost.objects.filter(pk=target_id, branch_id=user.branch_id, status=SocialPostStatus.PUBLISHED).first()
        content = target.caption if target else ""
        if target and target.media.exists():
            content = f"{content}\n[Attached media]"
    elif kind == TargetKind.COMMENT:
        target = SocialComment.objects.filter(pk=target_id, post__branch_id=user.branch_id, post__status=SocialPostStatus.PUBLISHED, status=SocialCommentStatus.PUBLISHED).select_related("post").first()
        if target and not visible(SocialPost.objects.filter(pk=target.post_id), TargetKind.POST).exists():
            target = None
        content = target.body if target else ""
    elif kind == TargetKind.GROUP_MESSAGE:
        target = GroupMessage.objects.filter(pk=target_id, group__branch_id=user.branch_id).select_related("group").first()
        if target:
            from apps.groups.views import CommunityMessageView

            if CommunityMessageView()._group(request, target.group_id) is None:
                target = None
        content = target.body if target else ""
    elif kind == TargetKind.GROUP_RESOURCE:
        target = GroupResource.objects.filter(pk=target_id, group__branch_id=user.branch_id).select_related("group").first()
        if target:
            from apps.groups.views import CommunityResourceView, _has_student_community_access

            if not _has_student_community_access(request) or CommunityResourceView()._membership(request, target.group_id) is None:
                target = None
        content = f"{target.title}\n{target.url}\n{target.description}" if target else ""
    elif kind == TargetKind.GROUP_ANNOUNCEMENT:
        from apps.groups.views import _has_student_community_access

        target = None
        if _has_student_community_access(request):
            target = Announcement.objects.filter(
                pk=target_id, branch_id=user.branch_id,
                target_groups__memberships__member__user=user,
                target_groups__memberships__is_active=True,
                status__in=[AnnouncementStatus.QUEUED, AnnouncementStatus.SENDING, AnnouncementStatus.COMPLETED],
            ).distinct().first()
        content = f"{target.title}\n{target.body}" if target else ""
    elif kind == TargetKind.PRAYER:
        prayer_scope = PrayerRequest.objects.filter(pk=target_id)
        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        if role not in Roles.GLOBAL_SCOPE_ROLES:
            prayer_scope = prayer_scope.filter(branch_id=user.branch_id)
        target = prayer_scope.first()
        if target and not can_moderate(user) and not (target.member and target.member.user_id == user.id) and not (
            target.privacy_level == "PUBLIC" and not target.is_private and target.consent_to_share
        ):
            target = None
        content = target.details if target else ""
    elif kind == TargetKind.TESTIMONY:
        testimony_scope = Testimony.objects.filter(pk=target_id)
        role = user.get_role_code() if hasattr(user, "get_role_code") else user.role
        if role not in Roles.GLOBAL_SCOPE_ROLES:
            testimony_scope = testimony_scope.filter(branch_id=user.branch_id)
        target = testimony_scope.first()
        if target and not can_moderate(user) and target.member.user_id != user.id:
            target = None
        content = f"{target.title}\n{target.details}" if target else ""
    else:
        target = None
        content = ""
    if not target or not visible(type(target).objects.filter(pk=target.pk), kind).exists():
        raise NotFound("This content is unavailable to report.")
    return target, content[:4000]


def target_author(kind, target_id):
    if kind == TargetKind.POST:
        target = SocialPost.objects.filter(pk=target_id).first()
        return target.author if target else None
    if kind == TargetKind.COMMENT:
        target = SocialComment.objects.filter(pk=target_id).first()
        return target.author if target else None
    if kind == TargetKind.GROUP_MESSAGE:
        target = GroupMessage.objects.filter(pk=target_id).first()
        return target.author if target else None
    if kind == TargetKind.GROUP_RESOURCE:
        target = GroupResource.objects.filter(pk=target_id).first()
        return target.created_by if target else None
    if kind == TargetKind.GROUP_ANNOUNCEMENT:
        target = Announcement.objects.filter(pk=target_id).first()
        return target.created_by if target else None
    if kind == TargetKind.PRAYER:
        target = PrayerRequest.objects.filter(pk=target_id).first()
        return target.member.user if target and target.member else None
    target = Testimony.objects.filter(pk=target_id).first()
    return target.member.user if target else None
