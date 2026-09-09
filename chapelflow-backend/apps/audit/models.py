import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password Change"
    ROLE_CHANGE = "ROLE_CHANGE", "Role Change"
    PERMISSION_CHANGE = "PERMISSION_CHANGE", "Permission Change"
    FINANCIAL_ACTION = "FINANCIAL_ACTION", "Financial Action"
    FINANCIAL_RECORD_VOIDED = "FINANCIAL_RECORD_VOIDED", "Financial Record Voided"
    FINANCIAL_RECORD_REFUNDED = "FINANCIAL_RECORD_REFUNDED", "Financial Record Refunded"
    MEMBER_RECORD_ACCESS = "MEMBER_RECORD_ACCESS", "Member Record Access"
    MEMBER_DEACTIVATE = "MEMBER_DEACTIVATE", "Member Deactivate"
    MEMBER_REACTIVATE = "MEMBER_REACTIVATE", "Member Reactivate"
    MEMBER_MERGE = "MEMBER_MERGE", "Member Merge"
    MEMBER_TRANSFER = "MEMBER_TRANSFER", "Member Transfer"
    GROUP_LEADERSHIP_CHANGE = "GROUP_LEADERSHIP_CHANGE", "Group Leadership Change"
    MEMBER_SELF_REGISTER = "MEMBER_SELF_REGISTER", "Member Self Registration"
    VISITOR_FOLLOW_UP = "VISITOR_FOLLOW_UP", "Visitor Follow Up"
    BRANCH_CHANGE = "BRANCH_CHANGE", "Branch Change"
    EVENT_CHANGE = "EVENT_CHANGE", "Event Change"
    COMMUNICATION_ACTION = "COMMUNICATION_ACTION", "Communication Action"
    MFA_ENROLL = "MFA_ENROLL", "MFA Enroll"
    MFA_ENABLE = "MFA_ENABLE", "MFA Enable"
    MFA_RESET = "MFA_RESET", "MFA Administrative Reset"
    # Phase 13: Prayer & Pastoral Care
    PASTORAL_CASE_CREATE = "PASTORAL_CASE_CREATE", "Pastoral Case Create"
    PASTORAL_CASE_ASSIGN = "PASTORAL_CASE_ASSIGN", "Pastoral Case Assign"
    PASTORAL_CASE_STATUS_CHANGE = "PASTORAL_CASE_STATUS_CHANGE", "Pastoral Case Status Change"
    PASTORAL_CASE_ESCALATE = "PASTORAL_CASE_ESCALATE", "Pastoral Case Escalate"
    PASTORAL_CASE_CLOSE = "PASTORAL_CASE_CLOSE", "Pastoral Case Close"
    PASTORAL_CASE_ACCESS = "PASTORAL_CASE_ACCESS", "Pastoral Case Access"
    PASTORAL_NOTE_CREATE = "PASTORAL_NOTE_CREATE", "Pastoral Note Create"
    PRAYER_REQUEST_CREATE = "PRAYER_REQUEST_CREATE", "Prayer Request Create"
    PRAYER_REQUEST_ASSIGN = "PRAYER_REQUEST_ASSIGN", "Prayer Request Assign"
    PRAYER_REQUEST_STATUS_CHANGE = "PRAYER_REQUEST_STATUS_CHANGE", "Prayer Request Status Change"
    PRAYER_REQUEST_CLOSE = "PRAYER_REQUEST_CLOSE", "Prayer Request Close"
    PRAYER_REQUEST_ACCESS = "PRAYER_REQUEST_ACCESS", "Prayer Request Access"
    PRAYER_NOTE_CREATE = "PRAYER_NOTE_CREATE", "Prayer Note Create"
    # Phase 14: Finance Reconciliation & Controls
    FINANCIAL_PERIOD_CLOSED = "FINANCIAL_PERIOD_CLOSED", "Financial Period Closed"
    FINANCIAL_PERIOD_LOCKED = "FINANCIAL_PERIOD_LOCKED", "Financial Period Locked"
    FINANCIAL_PERIOD_REOPENED = "FINANCIAL_PERIOD_REOPENED", "Financial Period Reopened"
    RECONCILIATION_CREATED = "RECONCILIATION_CREATED", "Reconciliation Created"
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED", "Reconciliation Started"
    RECONCILIATION_COMPLETED = "RECONCILIATION_COMPLETED", "Reconciliation Completed"
    RECONCILIATION_APPROVED = "RECONCILIATION_APPROVED", "Reconciliation Approved"
    ADJUSTMENT_CREATED = "ADJUSTMENT_CREATED", "Financial Adjustment Created"
    ADJUSTMENT_APPROVED = "ADJUSTMENT_APPROVED", "Financial Adjustment Approved"
    ADJUSTMENT_REJECTED = "ADJUSTMENT_REJECTED", "Financial Adjustment Rejected"
    ADJUSTMENT_APPLIED = "ADJUSTMENT_APPLIED", "Financial Adjustment Applied"


class AuditLog(models.Model):
    """
    Immutable by convention: no view/admin in this app ever exposes
    update or delete for this model (see admin.py — readonly, no delete
    permission for non-superusers).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
        ]
        ordering = ["-created_at"]
