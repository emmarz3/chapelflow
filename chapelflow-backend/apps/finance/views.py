import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.viewsets import StandardModelViewSet, StandardReadOnlyModelViewSet
from common.constants.roles import PermissionCodes
from common.permissions.rbac import IsFinanceAuthorized
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from .models import FinancialStatement, Giving, GivingCategory, GivingStatus, Payment, PaymentStatus, Pledge, Reconciliation, Refund
from .serializers import (
    FinancialStatementSerializer, GivingCategorySerializer, GivingSerializer,
    MemberGivingHistorySerializer, PaystackCheckoutSerializer, PaystackReferenceSerializer,
    PaymentSerializer, PledgeSerializer,
    ReconciliationSerializer, RefundSerializer,
)
from .services import (
    PaymentProviderError,
    WebhookVerificationError,
    initialize_paystack_checkout,
    process_webhook,
    verify_paystack_transaction,
)


class GivingCategoryViewSet(StandardModelViewSet):
    queryset = GivingCategory.objects.all().order_by("name")
    serializer_class = GivingCategorySerializer
    permission_classes = [IsFinanceAuthorized]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
        "create": PermissionCodes.FINANCE_CREATE,
        "update": PermissionCodes.FINANCE_UPDATE,
        "partial_update": PermissionCodes.FINANCE_UPDATE,
        "destroy": PermissionCodes.FINANCE_DELETE,
    }


class GivingViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 8 hardened: Staff-only giving record management with immutability protection.
    
    Security:
    - Branch-scoped querysets (BranchScopedQuerysetMixin)
    - Finance authorization required (MFA + FINANCE_ACCESS_ROLES)
    - Server-controlled branch/member/recorded_by/given_at
    - Immutability: CONFIRMED records cannot be modified via PATCH
    """
    serializer_class = GivingSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["branch", "member", "category", "source", "status", "event", "group"]
    ordering_fields = ["given_at", "amount"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
        "create": PermissionCodes.FINANCE_CREATE,
        "update": PermissionCodes.FINANCE_UPDATE,
        "partial_update": PermissionCodes.FINANCE_UPDATE,
        "destroy": PermissionCodes.FINANCE_DELETE,
        "void": PermissionCodes.FINANCE_UPDATE,
    }

    def get_base_queryset(self):
        return Giving.objects.select_related("branch", "member", "category", "payment", "event", "group")

    def perform_create(self, serializer):
        """
        Phase 8: Server-controlled fields.
        - recorded_by: Always request.user
        - given_at: Server timestamp (timezone.now())
        - branch: Derived from user's branch if not explicitly provided
        - status: Always CONFIRMED for staff-recorded giving
        """
        user = self.request.user
        serializer.save(
            recorded_by=user,
            given_at=timezone.now(),
            branch=serializer.validated_data.get('branch', user.branch),
            status=GivingStatus.CONFIRMED
        )
    
    def perform_update(self, serializer):
        """
        Phase 8: Immutability protection.
        CONFIRMED records cannot be modified. Use void action instead.
        """
        instance = self.get_object()
        if instance.status == GivingStatus.CONFIRMED:
            # Only allow updating note field on confirmed records
            if set(serializer.validated_data.keys()) - {'note'}:
                raise serializers.ValidationError({
                    "status": "Cannot modify confirmed giving records. Use the void action to cancel."
                })
        serializer.save()
    
    def perform_destroy(self, instance):
        """
        Phase 8: Soft delete via void action is preferred.
        Hard delete only allowed for non-confirmed records.
        """
        if instance.status == GivingStatus.CONFIRMED:
            raise serializers.ValidationError({
                "status": "Cannot delete confirmed giving records. Use the void action instead."
            })
        instance.delete()
    
    @action(detail=True, methods=['post'], url_path='void')
    def void(self, request, pk=None):
        """
        Phase 8: Void a giving record (soft delete with audit trail).
        
        POST /api/v1/giving/{id}/void/
        
        Body: {"reason": "Reason for voiding"}
        
        Security: Requires FINANCE_UPDATE permission.
        """
        giving = self.get_object()
        
        if giving.status == GivingStatus.VOIDED:
            return error_response("Giving record is already voided.", status=400)
        
        reason = request.data.get('reason', '')
        if not reason:
            return error_response("Reason for voiding is required.", status=400)
        
        with transaction.atomic():
            # Update status
            giving.status = GivingStatus.VOIDED
            giving.note = f"[VOIDED: {reason}] {giving.note}"
            giving.save(update_fields=['status', 'note'])
            
            # Audit log
            from apps.audit.services import write_audit_log
            from apps.audit.models import AuditAction
            write_audit_log(
                user=request.user,
                action=AuditAction.FINANCIAL_RECORD_VOIDED,
                resource_type="Giving",
                resource_id=str(giving.id),
                metadata={"reason": reason, "original_amount": str(giving.amount)}
            )
        
        serializer = self.get_serializer(giving)
        return Response(serializer.data)


class PledgeViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = PledgeSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["branch", "member", "category", "is_active"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
        "create": PermissionCodes.FINANCE_CREATE,
        "update": PermissionCodes.FINANCE_UPDATE,
        "partial_update": PermissionCodes.FINANCE_UPDATE,
        "destroy": PermissionCodes.FINANCE_DELETE,
    }

    def get_base_queryset(self):
        return Pledge.objects.select_related("branch", "member", "category")


class PaymentViewSet(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    """Payments are created by the frontend initiating a gateway transaction
    and updated only by verified webhooks — never edited directly here."""
    serializer_class = PaymentSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["branch", "member", "provider", "status"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
    }

    def get_base_queryset(self):
        return Payment.objects.select_related("branch", "member")


class FinancialStatementViewSet(BranchScopedQuerysetMixin, StandardReadOnlyModelViewSet):
    serializer_class = FinancialStatementSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["branch"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
    }

    def get_base_queryset(self):
        return FinancialStatement.objects.select_related("branch")


class ReconciliationViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = ReconciliationSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["branch"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
        "create": PermissionCodes.FINANCE_CREATE,
        "update": PermissionCodes.FINANCE_UPDATE,
        "partial_update": PermissionCodes.FINANCE_UPDATE,
        "destroy": PermissionCodes.FINANCE_DELETE,
    }

    def get_base_queryset(self):
        return Reconciliation.objects.select_related("branch")

    def perform_create(self, serializer):
        serializer.save(reconciled_by=self.request.user)


class RefundViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 8: Refund management.
    
    Security:
    - Finance authorization required
    - Branch-scoped (via original_giving.branch)
    - Validates refund amount does not exceed original
    - Creates audit trail
    """
    serializer_class = RefundSerializer
    permission_classes = [IsFinanceAuthorized]
    filterset_fields = ["original_giving"]
    permission_action_map = {
        "list": PermissionCodes.FINANCE_VIEW,
        "retrieve": PermissionCodes.FINANCE_VIEW,
        "create": PermissionCodes.FINANCE_CREATE,
    }

    def get_base_queryset(self):
        # Scope via original_giving's branch
        return Refund.objects.select_related("original_giving__branch", "original_giving__member")
    
    def get_queryset(self):
        """Phase 8: Apply branch scoping via original_giving."""
        user = self.request.user
        base_qs = self.get_base_queryset()
        
        # Use user's accessible branches
        from common.permissions.scoping import get_accessible_branch_ids
        accessible_branches = get_accessible_branch_ids(user)
        return base_qs.filter(original_giving__branch__in=accessible_branches)
    
    def perform_create(self, serializer):
        """Phase 8: Server-controlled refunded_by."""
        with transaction.atomic():
            refund = serializer.save(refunded_by=self.request.user)
            
            # Audit log
            from apps.audit.services import write_audit_log
            from apps.audit.models import AuditAction
            write_audit_log(
                user=self.request.user,
                action=AuditAction.FINANCIAL_RECORD_REFUNDED,
                resource_type="Giving",
                resource_id=str(refund.original_giving_id),
                metadata={
                    "refund_amount": str(refund.amount),
                    "reason": refund.reason,
                    "refund_id": str(refund.id)
                }
            )


class MemberGivingHistoryView(APIView):
    """
    Phase 8: Self-service member giving history.
    
    GET /api/v1/me/giving/
    
    Security:
    - Authenticated members only
    - Can only view own giving history (derived from request.user.member_profile)
    - Read-only
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get member profile from authenticated user
        member = getattr(request.user, 'member_profile', None)
        if not member:
            return error_response("No member profile linked to this account.", status=404)
        
        # Query only this member's giving records
        giving_records = Giving.objects.filter(
            member=member,
            status=GivingStatus.CONFIRMED  # Only show confirmed records
        ).select_related('category').order_by('-given_at')
        
        serializer = MemberGivingHistorySerializer(giving_records, many=True)
        return success_response({
            "giving_history": serializer.data,
            "total_count": giving_records.count()
        })


class MemberPledgeHistoryView(APIView):
    """
    Phase 8: Self-service member pledge history.
    
    GET /api/v1/me/pledges/
    
    Security:
    - Authenticated members only
    - Can only view own pledges
    - Read-only
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        member = getattr(request.user, 'member_profile', None)
        if not member:
            return error_response("No member profile linked to this account.", status=404)
        
        pledges = Pledge.objects.filter(member=member).select_related('category').order_by('-created_at')
        
        serializer = PledgeSerializer(pledges, many=True)
        return success_response({
            "pledges": serializer.data,
            "total_count": pledges.count()
        })


class MemberGivingSummaryView(APIView):
    """
    Phase 8: Self-service member giving summary.
    
    GET /api/v1/me/giving/summary/
    
    Security: Authenticated members only, own data only.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        member = getattr(request.user, 'member_profile', None)
        if not member:
            return error_response("No member profile linked to this account.", status=404)
        
        from .reports import member_giving_summary
        summary = member_giving_summary(member)
        
        return success_response(summary)


class FinancialDashboardView(APIView):
    """
    Phase 8: Branch financial dashboard.
    
    GET /api/v1/finance/dashboard/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    
    Security:
    - Finance authorization required
    - Branch-scoped (user's accessible branches)
    - All aggregations pre-filtered
    """
    permission_classes = [IsFinanceAuthorized]
    
    def get(self, request):
        from datetime import datetime
        from .reports import branch_financial_dashboard
        
        # Get date filters
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                return error_response("Invalid start_date format. Use YYYY-MM-DD.", status=400)
        
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                return error_response("Invalid end_date format. Use YYYY-MM-DD.", status=400)
        
        # Get user's branch (simplified - assumes single branch)
        # In production, this should aggregate across user's accessible branches
        branch = request.user.branch
        if not branch:
            return error_response("No branch associated with user.", status=400)
        
        dashboard_data = branch_financial_dashboard(branch, start_date, end_date)
        return success_response(dashboard_data)


class PaystackCheckoutInitializeView(APIView):
    """
    Starts an authenticated user's offering or tithe checkout.

    The browser receives a short-lived Paystack authorization URL only. The
    Paystack secret key, amount validation, category selection, and payer
    ownership remain server-side.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaystackCheckoutSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", errors=serializer.errors, status=400)

        user = request.user
        member = getattr(user, "member_profile", None)
        branch = member.branch if member else user.branch
        email = (user.email or (member.email if member else "")).strip()
        if not branch:
            return error_response("Your account is not linked to a chapel branch.", status=400)
        if not email:
            return error_response("Add an email address to your profile before giving online.", status=400)

        giving_type = serializer.validated_data["giving_type"]
        category = GivingCategory.objects.filter(
            name__iexact=giving_type.title(), is_active=True
        ).first()
        if not category:
            return error_response("Online giving is temporarily unavailable. Please contact the chapel office.", status=503)

        payment = Payment.objects.create(
            branch=branch,
            member=member,
            initiated_by=user,
            giving_category=category,
            giving_note=serializer.validated_data.get("note", ""),
            provider="PAYSTACK",
            provider_reference=f"CF-{uuid.uuid4().hex}",
            amount=serializer.validated_data["amount"],
            currency="NGN",
            idempotency_key=f"paystack-giving:{uuid.uuid4().hex}",
        )
        try:
            authorization_url = initialize_paystack_checkout(
                payment,
                email=email,
                callback_url=settings.PAYSTACK_CALLBACK_URL,
            )
        except PaymentProviderError as exc:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status"])
            return error_response(str(exc), status=503)

        return success_response(
            {"authorization_url": authorization_url, "reference": payment.provider_reference},
            message="Secure Paystack checkout created.",
            status=201,
        )


class PaystackCheckoutVerifyView(APIView):
    """Verifies only the signed-in payer's return reference with Paystack."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaystackReferenceSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", errors=serializer.errors, status=400)

        reference = serializer.validated_data["reference"]
        payment = Payment.objects.filter(
            provider="PAYSTACK",
            provider_reference=reference,
            initiated_by=request.user,
        ).select_related("giving_category").first()
        if not payment:
            return error_response("This payment reference does not belong to your account.", status=404)

        try:
            payment = verify_paystack_transaction(payment)
        except PaymentProviderError as exc:
            return error_response(str(exc), status=502)

        return success_response(
            {
                "reference": payment.provider_reference,
                "status": payment.status,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "giving_recorded": hasattr(payment, "giving_record"),
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PaymentWebhookView(APIView):
    """
    POST /api/v1/payments/webhook/<provider>/

    Public endpoint (gateways can't authenticate as a ChapelFlow user) but
    every request's signature is cryptographically verified before any
    state change happens, and processing is idempotent against replay.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider):
        try:
            payment = process_webhook(provider, request)
        except WebhookVerificationError as exc:
            return error_response(str(exc), status=400)
        return success_response({"reference": payment.provider_reference, "status": payment.status})
