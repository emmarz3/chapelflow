from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log
from apps.notifications.models import NotificationCategory, NotificationChannel
from apps.notifications.preferences import queue_notification
from common.constants.roles import Roles
from common.permissions.rbac import IsAuthenticatedAndActive
from common.utils.responses import success_response

from .models import ModerationEvent, ModerationReport, ModerationRestriction, ReportReason, ReportStatus, RestrictionState, TargetKind
from .services import can_moderate, scoped_reports, target_author, target_for_report


class ReportInput(serializers.Serializer):
    target_kind = serializers.ChoiceField(choices=TargetKind.choices)
    target_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=ReportReason.choices)
    explanation = serializers.CharField(max_length=1000, required=False, allow_blank=True, trim_whitespace=True)


def _notify(user, title, body):
    if user and user.is_active:
        queue_notification(recipient=user, category=NotificationCategory.ADMIN_ALERT, channel=NotificationChannel.IN_APP, title=title, body=body, href="/app/community-safety")


def _event(report, actor, action, note=""):
    event = ModerationEvent.objects.create(report=report, actor=actor, action=action, note=note)
    write_audit_log(
        action=AuditAction.UPDATE if action != "REPORT" else AuditAction.CREATE,
        resource_type="ModerationReport",
        resource_id=report.id,
        metadata={"action": action, "target_kind": report.target_kind, "target_id": str(report.target_id), "branch_id": str(report.branch_id)},
        user=actor,
    )
    return event


def _data(report, *, moderator=False):
    data = {
        "id": str(report.id), "target_kind": report.target_kind, "target_id": str(report.target_id),
        "reason": report.reason, "explanation": report.explanation, "status": report.status,
        "created_at": report.created_at, "reviewed_at": report.reviewed_at,
    }
    if moderator:
        data.update({
            "branch_id": str(report.branch_id), "reporter_id": str(report.reporter_id) if report.reporter_id else None,
            "content_snapshot": report.content_snapshot,
            "assigned_to_id": str(report.assigned_to_id) if report.assigned_to_id else None,
            "restriction": getattr(report, "restriction_state", None),
            "events": [{"action": event.action, "note": event.note, "actor_id": str(event.actor_id) if event.actor_id else None, "created_at": event.created_at} for event in report.events.all()],
        })
    return data


def _with_restriction(queryset):
    restriction = ModerationRestriction.objects.filter(
        branch_id=OuterRef("branch_id"), target_kind=OuterRef("target_kind"), target_id=OuterRef("target_id")
    ).values("state")[:1]
    return queryset.annotate(restriction_state=Subquery(restriction))


class ReportCollectionView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "moderation_report"
        return super().get_throttles()

    def get(self, request):
        reports = ModerationReport.objects.filter(reporter=request.user).order_by("-created_at")[:100]
        return success_response([_data(report) for report in reports])

    def post(self, request):
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        target, snapshot = target_for_report(request, values["target_kind"], values["target_id"])
        branch_id = target.post.branch_id if values["target_kind"] == TargetKind.COMMENT else (
            target.group.branch_id if values["target_kind"] in {TargetKind.GROUP_MESSAGE, TargetKind.GROUP_RESOURCE} else target.branch_id
        )
        if ModerationReport.objects.filter(
            reporter=request.user, target_kind=values["target_kind"], target_id=target.id,
            created_at__gte=timezone.now() - timedelta(hours=24),
        ).exists():
            raise ValidationError({"report": "You have already reported this content recently."})
        with transaction.atomic():
            report = ModerationReport.objects.create(
                branch_id=branch_id, reporter=request.user, target_kind=values["target_kind"],
                target_id=target.id, reason=values["reason"], explanation=values.get("explanation", ""),
                content_snapshot=snapshot, target_author=target_author(values["target_kind"], target.id),
            )
            _event(report, request.user, "REPORT")
            users = get_user_model().objects.filter(is_active=True).filter(
                Q(branch_id=branch_id) | Q(role=Roles.SUPER_ADMIN) | Q(role_obj__code=Roles.SUPER_ADMIN)
            ).distinct()
            for user in users:
                if user.id not in {request.user.id, report.target_author_id} and can_moderate(user):
                    _notify(user, "Community report received", "A community content report needs review.")
        return success_response(_data(report), message="Your report was sent for review.", status=201)


class ModerationQueueView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        status = request.query_params.get("status", ReportStatus.PENDING)
        if status not in ReportStatus.values and status != "ALL":
            raise ValidationError({"status": "Choose a valid report status."})
        reports = _with_restriction(scoped_reports(request.user)).select_related("reporter", "assigned_to").prefetch_related("events")
        if status != "ALL":
            reports = reports.filter(status=status)
        return success_response([_data(report, moderator=True) for report in reports.order_by("-created_at")[:100]])


class ModerationDetailView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        report = _with_restriction(scoped_reports(request.user)).prefetch_related("events").filter(pk=pk).first()
        if not report:
            raise NotFound("Report not found.")
        return success_response(_data(report, moderator=True))

    def post(self, request, pk):
        action = str(request.data.get("action", "")).upper()
        if action not in {"REVIEW", "DISMISS", "ESCALATE", "HIDE", "REMOVE", "RESTORE", "ASSIGN", "SUSPEND"}:
            raise ValidationError({"action": "Choose a valid moderation action."})
        raw_note = request.data.get("note", "")
        if not isinstance(raw_note, str):
            raise ValidationError({"note": "Provide a text note."})
        note = raw_note.strip()
        if len(note) > 2000:
            raise ValidationError({"note": "Keep moderator notes within 2,000 characters."})
        if action in {"DISMISS", "ESCALATE", "HIDE", "REMOVE", "SUSPEND"} and not note:
            raise ValidationError({"note": "Record a reason for this action."})
        role = request.user.get_role_code() if hasattr(request.user, "get_role_code") else request.user.role
        if action == "SUSPEND" and role != Roles.SUPER_ADMIN:
            raise PermissionDenied("Only a Super Admin can suspend an account.")
        with transaction.atomic():
            report = scoped_reports(request.user).select_for_update().filter(pk=pk).first()
            if not report:
                raise NotFound("Report not found.")
            if report.assigned_to_id is None:
                report.assigned_to = request.user
            if action in {"HIDE", "REMOVE"}:
                ModerationRestriction.objects.update_or_create(
                    branch=report.branch, target_kind=report.target_kind, target_id=report.target_id,
                    defaults={"state": RestrictionState.REMOVED if action == "REMOVE" else RestrictionState.HIDDEN},
                )
            elif action == "RESTORE":
                ModerationRestriction.objects.filter(branch=report.branch, target_kind=report.target_kind, target_id=report.target_id).delete()
            elif action == "ASSIGN":
                assignee_id = serializers.UUIDField().run_validation(request.data.get("assigned_to_id"))
                assignee = get_user_model().objects.filter(pk=assignee_id).first() if assignee_id else None
                if not assignee or not can_moderate(assignee) or (assignee.branch_id != report.branch_id and assignee.get_role_code() not in Roles.GLOBAL_SCOPE_ROLES):
                    raise ValidationError({"assigned_to_id": "Choose an authorized moderator for this branch."})
                report.assigned_to = assignee
            elif action == "SUSPEND":
                author = target_author(report.target_kind, report.target_id)
                if not author or author.id == request.user.id or author.get_role_code() in Roles.GLOBAL_SCOPE_ROLES:
                    raise ValidationError({"action": "This account cannot be suspended from this report."})
                author.is_active = False
                author.save(update_fields=["is_active"])
                ModerationRestriction.objects.update_or_create(
                    branch=report.branch, target_kind=report.target_kind, target_id=report.target_id,
                    defaults={"state": RestrictionState.HIDDEN},
                )
            if action != "ASSIGN":
                report.status = ReportStatus.DISMISSED if action == "DISMISS" else (
                    ReportStatus.ESCALATED if action == "ESCALATE" else ReportStatus.REVIEWED
                )
                report.reviewed_at = timezone.now()
            report.save(update_fields=["status", "reviewed_at", "assigned_to"])
            _event(report, request.user, action, note)
            if action in {"DISMISS", "ESCALATE", "HIDE", "REMOVE", "RESTORE", "SUSPEND"}:
                _notify(report.reporter, "Community report updated", f"Your report is now {report.status.lower()}.")
            if action in {"HIDE", "REMOVE", "RESTORE"}:
                author = target_author(report.target_kind, report.target_id)
                if author and author.id != report.reporter_id:
                    past_tense = {"HIDE": "hidden", "REMOVE": "removed", "RESTORE": "restored"}[action]
                    _notify(author, "Community content update", f"Your content has been {past_tense} by a chapel moderator.")
        report = _with_restriction(scoped_reports(request.user)).prefetch_related("events").get(pk=pk)
        return success_response(_data(report, moderator=True), message="Moderation action recorded.")
