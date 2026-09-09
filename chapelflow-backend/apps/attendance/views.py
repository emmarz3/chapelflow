from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from common.viewsets import StandardModelViewSet, StandardReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.utils import timezone
from django.db import models

from apps.members.models import Member, MemberQRCode
from common.constants.roles import PermissionCodes, Roles
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin, user_can_access_branch
from common.utils.responses import error_response, success_response
from .models import AttendanceCheckpoint, AttendanceCorrection, AttendanceRecord, AttendanceScanAttempt, AttendanceSession, AttendanceSessionState, CheckInDevice, VisitorAttendance
from .serializers import (
    AttendanceRecordSerializer, AttendanceSessionSerializer, CheckInDeviceSerializer,
    KioskCheckInSerializer, ManualCheckInSerializer, OfflineSyncRequestSerializer, QRCheckInSerializer,
    VisitorAttendanceSerializer,
)
from .services import (
    AttendanceError, issue_checkpoint_token, manual_check_in, qr_check_in,
    student_scan_usher_token, sync_offline_records,
)


class AttendanceSessionViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = AttendanceSessionSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "is_open", "event_schedule"]
    permission_action_map = {
        "list": PermissionCodes.ATTENDANCE_VIEW, "retrieve": PermissionCodes.ATTENDANCE_VIEW,
        "create": PermissionCodes.ATTENDANCE_CREATE, "update": PermissionCodes.ATTENDANCE_CREATE,
        "partial_update": PermissionCodes.ATTENDANCE_CREATE, "destroy": PermissionCodes.ATTENDANCE_CREATE,
        "close": PermissionCodes.ATTENDANCE_CREATE,
        "pause": PermissionCodes.ATTENDANCE_CREATE,
        "resume": PermissionCodes.ATTENDANCE_CREATE,
    }

    def get_base_queryset(self):
        return AttendanceSession.objects.select_related("branch", "event_schedule")
    
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """
        POST /api/v1/attendance/sessions/{id}/close/
        
        Closes attendance session, preventing further normal check-ins.
        Optionally generates absence records for registered members who
        didn't check in (if session is event-linked).
        """
        session = self.get_object()
        
        if not session.is_open:
            return error_response("Session already closed.", status=400)
        
        session.is_open = False
        session.state = AttendanceSessionState.CLOSED
        session.closed_at = timezone.now()
        session.save(update_fields=["is_open", "state", "closed_at"])
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.UPDATE, "attendance.AttendanceSession", session.id,
                        user=request.user, metadata={"transition": "closed"})
        
        # Optional: Generate absences for no-shows (event-linked sessions only)
        generate_absences = request.data.get("generate_absences", False)
        if generate_absences and session.event_schedule:
            from .services import generate_absences_for_session
            result = generate_absences_for_session(session)
            return success_response(
                AttendanceSessionSerializer(session).data,
                message=f"Session closed. {result['absences_created']} absence records generated."
            )
        
        return success_response(AttendanceSessionSerializer(session).data, message="Session closed.")

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        session = self.get_object()
        if not session.is_open or session.state != AttendanceSessionState.OPEN:
            return error_response("Only an open attendance session can be paused.", status=400)
        session.state = AttendanceSessionState.PAUSED
        session.save(update_fields=["state"])
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.UPDATE, "attendance.AttendanceSession", session.id,
                        user=request.user, metadata={"transition": "paused"})
        return success_response(AttendanceSessionSerializer(session).data, message="Attendance paused.")

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        session = self.get_object()
        if not session.is_open or session.state != AttendanceSessionState.PAUSED:
            return error_response("Only a paused attendance session can be resumed.", status=400)
        session.state = AttendanceSessionState.OPEN
        session.save(update_fields=["state"])
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.UPDATE, "attendance.AttendanceSession", session.id,
                        user=request.user, metadata={"transition": "resumed"})
        return success_response(AttendanceSessionSerializer(session).data, message="Attendance resumed.")


class AttendanceRecordViewSet(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    """
    Records are created only through the check-in/sync endpoints below,
    never directly, so duplicate-prevention and validation are always applied.

    Phase 1 fix: moved onto the shared scoping mixin (was hand-rolled
    branch-only scoping, missing Chaplain's org-wide visibility — same
    class of gap as VisitorAttendanceViewSet below).
    """
    serializer_class = AttendanceRecordSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["session", "member", "method"]
    permission_action_map = {
        "list": PermissionCodes.ATTENDANCE_VIEW,
        "retrieve": PermissionCodes.ATTENDANCE_VIEW,
        "analytics": PermissionCodes.ATTENDANCE_VIEW,
        "member_history": PermissionCodes.ATTENDANCE_VIEW,
        "check_out": PermissionCodes.ATTENDANCE_CREATE,
        "correct": PermissionCodes.ATTENDANCE_CREATE,
    }
    branch_field_lookup = "session__branch"

    def get_base_queryset(self):
        return AttendanceRecord.objects.select_related("session", "member", "device")

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """GET /api/v1/attendance-records/analytics/?days=90 -- spec Phase 8 attendance analytics, scoped to the caller."""
        from .services import attendance_analytics
        days = int(request.query_params.get("days", 90))
        return success_response(attendance_analytics(self.filter_queryset(self.get_queryset()), days=days))

    @action(detail=False, methods=["get"], url_path="member-history")
    def member_history(self, request):
        """GET /api/v1/attendance-records/member-history/?member_id=... -- spec Phase 8 member attendance history, scoped to the caller."""
        from .services import member_attendance_history
        member_id = request.query_params.get("member_id")
        if not member_id:
            return error_response("member_id is required.", status=400)
        return success_response(member_attendance_history(self.filter_queryset(self.get_queryset()), member_id))
    
    @action(detail=True, methods=["post"], url_path="check-out")
    def check_out(self, request, pk=None):
        """
        POST /api/v1/attendance/records/{id}/check-out/
        
        Phase 7 enhancement: Check-out tracking for duration calculation.
        Validates check-out time >= check-in time (server-controlled).
        """
        record = self.get_object()
        
        if record.checked_out_at:
            return error_response("Already checked out.", status=400)
        
        record.checked_out_at = timezone.now()
        record.save(update_fields=["checked_out_at"])
        
        return success_response(AttendanceRecordSerializer(record).data, message="Checked out successfully.")

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        """Correct a status only with an immutable reason and audit entry."""
        from .serializers import AttendanceCorrectionSerializer
        record = self.get_object()
        serializer = AttendanceCorrectionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        new_status = serializer.validated_data["status"]
        if record.status == new_status:
            return error_response("The attendance status is already set to that value.", status=400)
        correction = AttendanceCorrection.objects.create(
            record=record, previous_status=record.status, new_status=new_status,
            reason=serializer.validated_data["reason"], corrected_by=request.user,
        )
        record.status = new_status
        record.save(update_fields=["status"])
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(
            AuditAction.UPDATE, "attendance.AttendanceRecord", record.id, user=request.user,
            metadata={"correction_id": str(correction.id), "previous_status": correction.previous_status,
                      "new_status": correction.new_status, "reason": correction.reason},
        )
        return success_response(AttendanceRecordSerializer(record).data, message="Attendance corrected.")


class AttendanceScanAttemptViewSet(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    """Read-only, token-redacted scan outcomes for authorized administrators."""
    permission_classes = [HasRolePermission]
    permission_action_map = {"list": PermissionCodes.ATTENDANCE_VIEW, "retrieve": PermissionCodes.ATTENDANCE_VIEW}
    branch_field_lookup = "session__branch"

    class ScanAttemptSerializer(serializers.ModelSerializer):
        class Meta:
            model = AttendanceScanAttempt
            fields = ["id", "session", "checkpoint", "student", "result", "created_at"]
            read_only_fields = fields

    serializer_class = ScanAttemptSerializer
    filterset_fields = ["session", "checkpoint", "result"]

    def get_base_queryset(self):
        return AttendanceScanAttempt.objects.select_related("session", "checkpoint", "student")


class CheckInDeviceViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = CheckInDeviceSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "is_active"]
    permission_action_map = {
        "list": PermissionCodes.ATTENDANCE_VIEW, "retrieve": PermissionCodes.ATTENDANCE_VIEW,
        "create": PermissionCodes.ATTENDANCE_CREATE, "update": PermissionCodes.ATTENDANCE_CREATE,
        "partial_update": PermissionCodes.ATTENDANCE_CREATE, "destroy": PermissionCodes.ATTENDANCE_CREATE,
        "rotate_secret": PermissionCodes.ATTENDANCE_CREATE,
        "revoke": PermissionCodes.ATTENDANCE_CREATE,
    }

    def get_base_queryset(self):
        return CheckInDevice.objects.select_related("branch")

    @action(detail=True, methods=["post"], url_path="rotate-secret")
    def rotate_secret(self, request, pk=None):
        """
        POST /api/v1/check-in-devices/{id}/rotate-secret/
        Spec Phase 8: device credential rotation, independent of any user
        account. Returns the new secret ONCE, in plaintext, exactly like
        apps.members.MemberQRCode.regenerate() -- it is never stored or
        retrievable again after this response; only its hash persists.
        """
        import secrets
        device = self.get_object()
        new_secret = secrets.token_urlsafe(32)
        device.set_secret(new_secret)
        device.is_active = True
        device.save(update_fields=["secret_hash", "is_active"])
        return success_response(
            {"device_id": str(device.id), "device_secret": new_secret},
            message="Store this secret securely on the device now -- it will not be shown again.",
        )

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """POST /api/v1/check-in-devices/{id}/revoke/ -- immediately blocks this device from checking anyone in, without touching any user account."""
        device = self.get_object()
        device.is_active = False
        device.save(update_fields=["is_active"])
        return success_response(CheckInDeviceSerializer(device).data, message="Device revoked.")


class VisitorAttendanceViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """Phase 1 fix: same de-duplication/Chaplain-scope fix as AttendanceRecordViewSet above."""
    serializer_class = VisitorAttendanceSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["session", "follow_up_status"]
    permission_action_map = {
        "list": PermissionCodes.ATTENDANCE_VIEW, "retrieve": PermissionCodes.ATTENDANCE_VIEW,
        "create": PermissionCodes.ATTENDANCE_CREATE, "update": PermissionCodes.ATTENDANCE_CREATE,
        "partial_update": PermissionCodes.ATTENDANCE_CREATE, "destroy": PermissionCodes.ATTENDANCE_CREATE,
    }
    branch_field_lookup = "session__branch"

    def get_base_queryset(self):
        return VisitorAttendance.objects.select_related("session", "invited_by")


class QRCheckInView(APIView):
    """Staff-only legacy scan of a member's personal QR.

    Students cannot use this endpoint; self-attendance is exclusively the
    live usher-token endpoint below.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.get_role_code() == "MEMBER":
            return error_response("Students must scan a live usher QR code to record attendance.", status=403)
        serializer = QRCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = AttendanceSession.objects.filter(id=data["session_id"]).first()
        if not session or not user_can_access_branch(request.user, session.branch_id):
            return error_response("Attendance session not found.", status=404)

        device = None
        if data.get("device_id"):
            device = CheckInDevice.objects.filter(id=data["device_id"]).first()

        try:
            record, created = qr_check_in(
                token=data["token"], session=session, device=device, checked_in_by=request.user,
            )
        except AttendanceError as exc:
            return error_response(str(exc), status=400)

        message = "Checked in successfully." if created else "Already checked in for this session."
        return success_response(AttendanceRecordSerializer(record).data, message=message, status=201 if created else 200)


class UsherCheckpointTokenView(APIView):
    """Return only the logged-in usher's live QR for the current service."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.get_role_code() != "ATTENDANCE_USHER":
            return error_response("This attendance checkpoint is restricted to usher accounts.", status=403)
        session = AttendanceSession.objects.filter(
            is_open=True, state=AttendanceSessionState.OPEN,
        ).order_by("-opened_at").first()
        if not session:
            return error_response("No attendance session is currently open.", status=404)
        try:
            checkpoint, _ = AttendanceCheckpoint.objects.get_or_create(session=session, usher=request.user)
            token = issue_checkpoint_token(checkpoint)
        except AttendanceError as exc:
            return error_response(str(exc), status=400)
        return success_response({
            "checkpoint_id": str(checkpoint.id),
            "checkpoint_name": request.user.full_name or "Attendance checkpoint",
            "successful_scans": AttendanceRecord.objects.filter(checkpoint=checkpoint).count(),
            "session": AttendanceSessionSerializer(session).data,
            **token,
        })


class StudentUsherScanView(APIView):
    """Record the authenticated student's scan of an usher's live QR token."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "attendance_scan"

    def post(self, request):
        from .serializers import StudentUsherScanSerializer
        serializer = StudentUsherScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record, created = student_scan_usher_token(
                token=serializer.validated_data["token"], user=request.user,
            )
        except AttendanceError as exc:
            return error_response(str(exc), status=400)
        return success_response(
            {"record": AttendanceRecordSerializer(record).data, "result": "recorded" if created else "duplicate"},
            message="Attendance recorded." if created else "Attendance has already been recorded.",
            status=201 if created else 200,
        )


class ManualCheckInView(APIView):
    """POST /api/v1/attendance/manual/"""
    permission_classes = [HasRolePermission]
    permission_action_map = {"post": PermissionCodes.ATTENDANCE_CREATE}

    def post(self, request):
        serializer = ManualCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = AttendanceSession.objects.filter(id=data["session_id"]).first()
        if not session or not user_can_access_branch(request.user, session.branch_id):
            return error_response("Attendance session not found.", status=404)

        member = Member.objects.filter(id=data["member_id"], branch_id=session.branch_id).first()
        if not member:
            return error_response("Member not found in this branch.", status=404)

        record, created = manual_check_in(member=member, session=session, checked_in_by=request.user)
        message = "Checked in successfully." if created else "Already checked in for this session."
        return success_response(AttendanceRecordSerializer(record).data, message=message, status=201 if created else 200)


class KioskCheckInView(APIView):
    """POST /api/v1/attendance/check-in/  (device-authenticated kiosk endpoint)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = KioskCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        session = AttendanceSession.objects.filter(id=data["session_id"]).first()
        if not session:
            return error_response("Attendance session not found.", status=404)

        # Deliberately NOT filtering by is_active here: kiosk_check_in()
        # itself must be the one to reject an inactive device (with a
        # clear "deactivated" error) rather than this view silently
        # treating an inactive device the same as a nonexistent one.
        device = CheckInDevice.objects.filter(id=data["device_id"]).first()
        if device is None:
            return error_response("Device not found.", status=404)

        from .services import kiosk_check_in
        try:
            record, created = kiosk_check_in(
                token=data["token"], session=session, device=device, device_secret=data["device_secret"],
            )
        except AttendanceError as exc:
            return error_response(str(exc), status=400)

        message = "Checked in successfully." if created else "Already checked in for this session."
        return success_response(AttendanceRecordSerializer(record).data, message=message, status=201 if created else 200)


class OfflineSyncView(APIView):
    """
    POST /api/v1/attendance/sync/

    Idempotent: safe to call repeatedly with the same records (e.g. after
    a dropped connection). Each record's client_record_id determines
    whether it's a new record or a no-op re-submission.
    """
    permission_classes = [HasRolePermission]
    permission_action_map = {"post": PermissionCodes.ATTENDANCE_CREATE}
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "sync"

    def post(self, request):
        serializer = OfflineSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        branch_id = request.user.branch_id
        from common.constants.roles import Roles
        if request.user.role in Roles.GLOBAL_SCOPE_ROLES:
            # Global roles must specify which branch this offline batch belongs to
            # via the first record's session; validated per-record in the service.
            branch = None
        else:
            from apps.organizations.models import Branch
            branch = Branch.objects.filter(id=branch_id).first()
            if not branch:
                return error_response("No branch assigned to this account.", status=403)

        if branch is None:
            # Resolve branch from the sessions referenced in the payload (super admin path).
            from .models import AttendanceSession as Sess
            session_ids = {r["session_id"] for r in serializer.validated_data["records"]}
            branches = set(Sess.objects.filter(id__in=session_ids).values_list("branch_id", flat=True))
            if len(branches) != 1:
                return error_response("Offline batch must belong to a single branch.", status=400)
            from apps.organizations.models import Branch
            branch = Branch.objects.get(id=branches.pop())

        results = sync_offline_records(
            records=serializer.validated_data["records"], branch=branch, submitted_by=request.user,
        )
        return success_response({"results": results}, message="Sync processed.")


class MemberAttendancePassView(APIView):
    """Return the authenticated member's display-safe attendance pass state."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.get_role_code() != Roles.MEMBER:
            return error_response("This pass is available only to student accounts.", status=403)
        member = Member.objects.select_related("department").filter(user=request.user).first()
        if not member:
            return error_response("No member profile associated with this account.", status=403)
        session = (
            AttendanceSession.objects.filter(branch=member.branch, is_open=True)
            .order_by("-opened_at")
            .first()
        )
        now = timezone.now()
        completed_sessions = AttendanceSession.objects.filter(branch=member.branch).filter(
            models.Q(state=AttendanceSessionState.CLOSED)
            | models.Q(window_closes_at__lt=now)
        )
        attended_services = AttendanceRecord.objects.filter(member=member).values("session_id").distinct().count()
        total_services = completed_sessions.count()
        session_state = None
        if session is not None:
            session_state = session.state.lower()
            if session.window_opens_at and session.window_opens_at > now:
                session_state = "upcoming"
        return success_response({
            "student": {
                "name": member.full_name,
                "identifier": request.user.matric_no or request.user.email or "",
                "programme": getattr(member.department, "name", None),
                "level": None,
                "photoUrl": member.photo_url or None,
            },
            "passStatus": "active" if member.membership_status == "ACTIVE" else "inactive",
            "session": None if session is None else {
                "id": str(session.id),
                "title": session.label or "Chapel service",
                "state": session_state,
                "opens_at": session.window_opens_at or session.opened_at,
                "closes_at": session.window_closes_at,
            },
            # A student's identity QR is deliberately not returned here. It
            # lives behind a separate self-only endpoint and is never accepted
            # by the live usher-token scanner.
            "token": None,
            "imageDataUrl": None,
            "expiresAt": None,
            "attendance_summary": {
                "total_services": total_services,
                "attended_services": attended_services,
                "missed_services": max(total_services - attended_services, 0),
                "percentage": round((attended_services / total_services) * 100) if total_services else None,
            },
        })


class MemberIdentityPassView(APIView):
    """Return the caller's opaque, self-only chapel identity QR token.

    This is not a student self-service attendance credential. The student
    scan endpoint accepts only short-lived signed usher checkpoint tokens, so
    presenting this pass cannot self-register the student for a service.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.get_role_code() != Roles.MEMBER:
            return error_response("This pass is available only to student accounts.", status=403)
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return error_response("No member profile associated with this account.", status=403)
        qr, _ = MemberQRCode.objects.get_or_create(member=member)
        if not qr.is_active:
            return error_response("Your chapel identity pass is inactive.", status=403)
        return success_response({"token": qr.token, "issued_at": qr.created_at})


class MemberAttendanceHistoryView(APIView):
    """Return only the caller's attendance records, newest first."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return error_response("No member profile associated with this account.", status=403)
        records = AttendanceRecord.objects.filter(member=member).select_related("session").order_by("-checked_in_at")[:100]
        return success_response([
            {
                "title": record.session.label or "Chapel service",
                "date": record.checked_in_at,
                "recorded_at": record.checked_in_at,
                "status": str(record.status).lower(),
            }
            for record in records
        ])


class SelfCheckInView(APIView):
    """
    POST /api/v1/attendance/self-check-in/
    
    CRITICAL Phase 7 security enhancement: Member self-check-in endpoint
    that derives member from authenticated user, preventing impersonation.
    
    Unlike QRCheckInView (which accepts any QR token), this endpoint:
    - Derives member from request.user.member relationship
    - Does NOT accept member_id or token from client
    - Prevents Member A from checking in as Member B
    - Intended for mobile app self-service check-in
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from .serializers import SelfCheckInSerializer
        serializer = SelfCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # CRITICAL: Derive member from authenticated user (server-side)
        member = Member.objects.filter(user=request.user).first()
        if not member:
            return error_response("No member profile associated with this account.", status=403)
        
        session = AttendanceSession.objects.filter(id=data["session_id"]).first()
        if not session:
            return error_response("Attendance session not found.", status=404)
        
        # Validate session is open
        if not session.is_open:
            return error_response("This attendance session is closed.", status=400)
        
        # Validate member can access session's branch
        if not user_can_access_branch(request.user, session.branch_id):
            return error_response("Attendance session not found.", status=404)  # Don't leak existence
        
        # Validate member belongs to session's branch
        if member.branch_id != session.branch_id:
            return error_response("Cannot check in to another branch's session.", status=403)
        
        from .services import self_check_in
        try:
            record, created = self_check_in(member=member, session=session)
        except AttendanceError as exc:
            return error_response(str(exc), status=400)
        
        message = "Checked in successfully." if created else "Already checked in for this session."
        return success_response(AttendanceRecordSerializer(record).data, message=message, status=201 if created else 200)
