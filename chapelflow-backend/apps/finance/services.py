import hashlib
import hmac
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from .models import Payment, PaymentStatus

payments_logger = logging.getLogger("chapelflow.payments")


class WebhookVerificationError(Exception):
    pass


class PaymentService:
    """Base interface every gateway-specific service implements."""

    provider_code: str

    def verify_webhook_signature(self, request) -> bool:
        raise NotImplementedError

    def parse_webhook_event(self, payload: dict) -> dict:
        """Returns {'reference': str, 'status': PaymentStatus, 'amount': Decimal}."""
        raise NotImplementedError


class PaystackService(PaymentService):
    provider_code = "PAYSTACK"

    def verify_webhook_signature(self, request) -> bool:
        secret = settings.PAYSTACK_SECRET_KEY.encode()
        signature = request.headers.get("X-Paystack-Signature", "")
        computed = hmac.new(secret, request.body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(signature, computed)

    def parse_webhook_event(self, payload: dict) -> dict:
        data = payload.get("data", {})
        status_map = {"success": PaymentStatus.SUCCESSFUL, "failed": PaymentStatus.FAILED}
        
        # Convert kobo to naira using Decimal for precision
        amount_kobo = data.get("amount") or 0
        amount_naira = Decimal(str(amount_kobo)) / Decimal("100")
        
        return {
            "reference": data.get("reference"),
            "status": status_map.get(payload.get("event", "").split(".")[-1], PaymentStatus.PENDING),
            "amount": amount_naira,
        }


class FlutterwaveService(PaymentService):
    provider_code = "FLUTTERWAVE"

    def verify_webhook_signature(self, request) -> bool:
        expected = settings.FLUTTERWAVE_SECRET_KEY
        provided = request.headers.get("verif-hash", "")
        return hmac.compare_digest(provided, expected)

    def parse_webhook_event(self, payload: dict) -> dict:
        data = payload.get("data", {})
        status_map = {"successful": PaymentStatus.SUCCESSFUL, "failed": PaymentStatus.FAILED}
        return {
            "reference": data.get("tx_ref"),
            "status": status_map.get(data.get("status"), PaymentStatus.PENDING),
            "amount": data.get("amount"),
        }


PROVIDER_SERVICES = {
    "paystack": PaystackService(),
    "flutterwave": FlutterwaveService(),
}


def process_webhook(provider_key: str, request) -> Payment:
    """
    Verifies the webhook is genuinely from the gateway, then applies the
    status update idempotently: re-delivery of the same event (gateways
    routinely retry webhooks) is a safe no-op once the payment is already
    in a terminal state.
    """
    service = PROVIDER_SERVICES.get(provider_key)
    if not service:
        raise WebhookVerificationError(f"Unknown payment provider: {provider_key}")

    if not service.verify_webhook_signature(request):
        payments_logger.warning("webhook_signature_invalid provider=%s", provider_key)
        raise WebhookVerificationError("Invalid webhook signature.")

    import json
    payload = json.loads(request.body)
    event = service.parse_webhook_event(payload)

    if not event.get("reference"):
        raise WebhookVerificationError("Webhook payload missing a transaction reference.")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            provider_reference=event["reference"]
        ).first()

        if payment is None:
            payments_logger.warning(
                "webhook_unknown_reference provider=%s reference=%s", provider_key, event["reference"]
            )
            raise WebhookVerificationError("No matching payment record for this reference.")

        if payment.status in (PaymentStatus.SUCCESSFUL, PaymentStatus.FAILED, PaymentStatus.REFUNDED):
            # Already in a terminal state -> idempotent no-op, even if the
            # gateway redelivers the same webhook multiple times.
            payments_logger.info("webhook_idempotent_skip reference=%s status=%s", event["reference"], payment.status)
            return payment

        from django.utils import timezone
        payment.status = event["status"]
        payment.raw_webhook_payload = payload
        if event["status"] == PaymentStatus.SUCCESSFUL:
            payment.confirmed_at = timezone.now()
        payment.save(update_fields=["status", "raw_webhook_payload", "confirmed_at"])

        payments_logger.info(
            "webhook_processed provider=%s reference=%s status=%s", provider_key, event["reference"], payment.status
        )

    return payment



def reconcile_gateway_transactions(branch, period_start, period_end):
    """
    Phase 14: Match gateway transactions with internal giving records.
    
    Compares:
    - Gateway payments (Payment model) in period
    - Internal giving records (Giving model) in period
    
    Returns dict with:
    - matched: [(payment, giving), ...] - Perfect matches
    - unmatched_payments: [payment, ...] - Payments without giving records
    - unmatched_giving: [giving, ...] - Giving records without payments
    - mismatches: [(payment, giving, differences), ...] - Linked but mismatched
    
    Match criteria:
    - Same amount
    - Same currency
    - Same member
    - Payment.giving_record links to Giving
    
    Used by:
    - Daily automated reconciliation task
    - Manual reconciliation review (finance dashboard)
    - Month-end closing process
    """
    from decimal import Decimal
    from .models import Payment, Giving, PaymentStatus, GivingStatus, GivingSource
    
    # Get successful payments in period
    payments = Payment.objects.filter(
        branch=branch,
        status=PaymentStatus.SUCCESSFUL,
        confirmed_at__gte=period_start,
        confirmed_at__lte=period_end
    ).select_related('member')
    
    # Get online giving records in period
    giving_records = Giving.objects.filter(
        branch=branch,
        source=GivingSource.ONLINE,
        status=GivingStatus.CONFIRMED,
        given_at__gte=period_start,
        given_at__lte=period_end
    ).select_related('member', 'payment')
    
    matched = []
    mismatches = []
    unmatched_payments = []
    unmatched_giving = list(giving_records)
    
    for payment in payments:
        # Try to find linked giving record
        if hasattr(payment, 'giving_record') and payment.giving_record:
            giving = payment.giving_record
            
            # Verify match quality
            differences = []
            
            # Check amount (allow small rounding differences)
            if abs(payment.amount - giving.amount) > Decimal('0.01'):
                differences.append({
                    "field": "amount",
                    "payment": str(payment.amount),
                    "giving": str(giving.amount),
                    "difference": str(payment.amount - giving.amount)
                })
            
            # Check currency
            if payment.currency != giving.currency:
                differences.append({
                    "field": "currency",
                    "payment": payment.currency,
                    "giving": giving.currency
                })
            
            # Check member
            if payment.member_id != giving.member_id:
                differences.append({
                    "field": "member",
                    "payment": str(payment.member_id) if payment.member_id else None,
                    "giving": str(giving.member_id) if giving.member_id else None
                })
            
            if differences:
                # Linked but mismatched
                mismatches.append((payment, giving, differences))
            else:
                # Perfect match
                matched.append((payment, giving))
            
            # Remove from unmatched list
            if giving in unmatched_giving:
                unmatched_giving.remove(giving)
        else:
            # Payment without giving record
            unmatched_payments.append(payment)
    
    return {
        "matched": matched,
        "unmatched_payments": unmatched_payments,
        "unmatched_giving": unmatched_giving,
        "mismatches": mismatches,
        "summary": {
            "total_payments": payments.count(),
            "total_giving": giving_records.count(),
            "matched_count": len(matched),
            "mismatch_count": len(mismatches),
            "unmatched_payment_count": len(unmatched_payments),
            "unmatched_giving_count": len(unmatched_giving)
        }
    }


def auto_create_giving_from_payment(payment):
    """
    Phase 14: Automatically create Giving record from successful Payment.
    
    Called by webhook processor after payment confirmation.
    
    Args:
        payment: Payment instance (status=SUCCESSFUL)
    
    Returns:
        Giving instance or None if already exists
    
    Idempotency:
    - Checks if giving_record already linked
    - Only creates if missing
    
    Security:
    - Respects branch boundaries
    - Uses payment metadata for category/member
    """
    # Check if giving already exists
    if hasattr(payment, 'giving_record') and payment.giving_record:
        return payment.giving_record
    
    # Find default online giving category
    from .models import Giving, GivingCategory, GivingSource, GivingStatus
    
    default_category = GivingCategory.objects.filter(
        name__icontains="online"
    ).first() or GivingCategory.objects.first()
    
    if not default_category:
        logger.warning(f"No giving category found for payment {payment.id}")
        return None
    
    # Create giving record
    giving = Giving.objects.create(
        branch=payment.branch,
        member=payment.member,
        category=default_category,
        amount=payment.amount,
        currency=payment.currency,
        source=GivingSource.ONLINE,
        status=GivingStatus.CONFIRMED,
        payment=payment,
        given_at=payment.confirmed_at or payment.created_at,
        note=f"Auto-created from payment {payment.provider}:{payment.provider_reference}"
    )
    
    logger.info(
        f"Auto-created giving {giving.id} from payment {payment.id} "
        f"(amount: {payment.amount} {payment.currency})"
    )
    
    # Phase 12: Check if this giving fulfills any pledges
    fulfill_pledge_from_giving(giving)
    
    return giving


def fulfill_pledge_from_giving(giving):
    """
    Phase 12: Automatically fulfill pledges when giving is recorded.
    
    Matches giving to open pledges and marks fulfillment:
    - Same member
    - Same branch
    - Matching currency
    - Pledge not yet fulfilled
    - Amount matches or exceeds pledge
    
    Strategy:
    - Prioritizes oldest unfulfilled pledges first
    - Can partially fulfill multiple pledges
    - Updates pledge.fulfilled_amount
    - Marks pledge as fulfilled when amount_pledged == fulfilled_amount
    
    Called by:
    - Webhook processor (online giving)
    - Manual giving entry
    - Bulk giving import
    
    Args:
        giving: Giving instance
    
    Returns:
        list of (Pledge, amount_fulfilled) tuples
    """
    from .models import Pledge, PledgeStatus
    from decimal import Decimal
    
    if not giving.member:
        # Anonymous giving cannot be matched to pledges
        return []
    
    # Find unfulfilled pledges for this member
    unfulfilled_pledges = Pledge.objects.filter(
        member=giving.member,
        branch=giving.branch,
        currency=giving.currency,
        status=PledgeStatus.ACTIVE
    ).order_by('created_at')  # FIFO: fulfill oldest pledges first
    
    remaining_amount = giving.amount
    fulfilled = []
    
    for pledge in unfulfilled_pledges:
        if remaining_amount <= Decimal('0.00'):
            break
        
        # Calculate unfulfilled portion
        unfulfilled = pledge.amount_pledged - (pledge.fulfilled_amount or Decimal('0.00'))
        
        if unfulfilled <= Decimal('0.00'):
            # Pledge already fulfilled (shouldn't happen with status filter)
            continue
        
        # Determine how much to allocate to this pledge
        allocation = min(remaining_amount, unfulfilled)
        
        # Update pledge
        pledge.fulfilled_amount = (pledge.fulfilled_amount or Decimal('0.00')) + allocation
        
        # Check if pledge is now fully fulfilled
        if pledge.fulfilled_amount >= pledge.amount_pledged:
            pledge.status = PledgeStatus.FULFILLED
            pledge.fulfilled_at = giving.given_at
        
        pledge.save()
        
        fulfilled.append((pledge, allocation))
        remaining_amount -= allocation
        
        logger.info(
            f"Fulfilled pledge {pledge.id} with {allocation} {giving.currency} "
            f"from giving {giving.id} (pledge status: {pledge.status})"
        )
    
    return fulfilled
