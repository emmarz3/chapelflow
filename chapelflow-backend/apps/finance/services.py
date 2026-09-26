import hashlib
import hmac
import json
import logging
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

from .models import Payment, PaymentStatus

payments_logger = logging.getLogger("chapelflow.payments")


class WebhookVerificationError(Exception):
    pass


class PaymentProviderError(Exception):
    """A safe, user-facing failure while communicating with a payment gateway."""

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
        if not settings.PAYSTACK_SECRET_KEY:
            payments_logger.error("paystack_webhook_received_without_secret")
            return False
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
            "currency": data.get("currency", "NGN"),
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

        if payment.provider.lower() != provider_key:
            raise WebhookVerificationError("Payment provider does not match this transaction.")

        if Decimal(str(event["amount"])) != payment.amount or event.get("currency", payment.currency) != payment.currency:
            payments_logger.warning("webhook_payment_mismatch reference=%s", event["reference"])
            raise WebhookVerificationError("Payment amount or currency does not match this transaction.")

        if payment.status in (PaymentStatus.SUCCESSFUL, PaymentStatus.FAILED, PaymentStatus.REFUNDED):
            # Already in a terminal state -> idempotent no-op, even if the
            # gateway redelivers the same webhook multiple times.
            payments_logger.info("webhook_idempotent_skip reference=%s status=%s", event["reference"], payment.status)
            return payment

        payment = apply_gateway_result(payment, event["status"], payload)

        payments_logger.info(
            "webhook_processed provider=%s reference=%s status=%s", provider_key, event["reference"], payment.status
        )

    return payment


PAYSTACK_API_BASE_URL = "https://api.paystack.co"


def _paystack_request(path: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    """Call Paystack only from the server; the secret key is never sent to the browser."""
    secret = settings.PAYSTACK_SECRET_KEY
    if not secret:
        raise PaymentProviderError("Online giving is not configured yet. Please contact the chapel office.")

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{PAYSTACK_API_BASE_URL}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:  # nosec B310 - fixed Paystack HTTPS endpoint
            decoded = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        payments_logger.warning("paystack_api_request_failed path=%s error=%s", path, type(exc).__name__)
        raise PaymentProviderError("Paystack is temporarily unavailable. Please try again shortly.") from exc

    if not decoded.get("status") or not isinstance(decoded.get("data"), dict):
        payments_logger.warning("paystack_api_unsuccessful_response path=%s", path)
        raise PaymentProviderError("Paystack could not complete this request. Please try again shortly.")
    return decoded["data"]


def initialize_paystack_checkout(payment: Payment, *, email: str, callback_url: str = "") -> str:
    """Create a Paystack hosted checkout and return only its one-time authorization URL."""
    payload = {
        "email": email,
        "amount": str(int(payment.amount * Decimal("100"))),
        "currency": payment.currency,
        "reference": payment.provider_reference,
        "metadata": json.dumps(
            {
                "payment_id": str(payment.id),
                "giving_type": payment.giving_category.name if payment.giving_category else "Giving",
            }
        ),
    }
    if callback_url:
        payload["callback_url"] = callback_url

    response = _paystack_request("/transaction/initialize", method="POST", payload=payload)
    if response.get("reference") != payment.provider_reference or not response.get("authorization_url"):
        payments_logger.error("paystack_initialize_invalid_response reference=%s", payment.provider_reference)
        raise PaymentProviderError("Paystack could not start checkout. Please try again shortly.")
    return str(response["authorization_url"])


def apply_gateway_result(payment: Payment, payment_status: str, payload: dict) -> Payment:
    """Persist a verified provider result and create one immutable giving record when successful."""
    from django.utils import timezone

    payment.status = payment_status
    payment.raw_webhook_payload = payload
    if payment_status == PaymentStatus.SUCCESSFUL:
        payment.confirmed_at = timezone.now()
    payment.save(update_fields=["status", "raw_webhook_payload", "confirmed_at"])
    if payment_status == PaymentStatus.SUCCESSFUL:
        auto_create_giving_from_payment(payment)
    return payment


def verify_paystack_transaction(payment: Payment) -> Payment:
    """Verify a return reference with Paystack before recording it as successful."""
    response = _paystack_request(f"/transaction/verify/{quote(payment.provider_reference, safe='')}")
    amount = Decimal(str(response.get("amount", 0))) / Decimal("100")
    if (
        response.get("reference") != payment.provider_reference
        or amount != payment.amount
        or response.get("currency") != payment.currency
    ):
        payments_logger.warning("paystack_verify_mismatch reference=%s", payment.provider_reference)
        raise PaymentProviderError("Payment verification did not match this giving request.")

    status_map = {
        "success": PaymentStatus.SUCCESSFUL,
        "failed": PaymentStatus.FAILED,
        "abandoned": PaymentStatus.FAILED,
    }
    result_status = status_map.get(str(response.get("status", "")).lower(), PaymentStatus.PENDING)
    with transaction.atomic():
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked_payment.status in (PaymentStatus.SUCCESSFUL, PaymentStatus.FAILED, PaymentStatus.REFUNDED):
            return locked_payment
        return apply_gateway_result(locked_payment, result_status, response)



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
    
    # Respect the category selected before checkout. Older gateway payments
    # keep their previous online/default category fallback.
    from .models import Giving, GivingCategory, GivingSource, GivingStatus
    
    default_category = payment.giving_category or GivingCategory.objects.filter(
        name__icontains="online"
    ).first() or GivingCategory.objects.first()
    
    if not default_category:
        payments_logger.warning("payment_giving_category_missing payment=%s", payment.id)
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
        note=payment.giving_note or f"Online {payment.giving_category.name if payment.giving_category else 'giving'} via {payment.provider}."
    )
    
    payments_logger.info("giving_created_from_payment giving=%s payment=%s", giving.id, payment.id)
    
    # Phase 12: Check if this giving fulfills any pledges
    fulfill_pledge_from_giving(giving)
    
    return giving


def fulfill_pledge_from_giving(giving):
    """
    Phase 12: Automatically fulfill pledges when giving is recorded.
    
    Matches giving to open pledges and marks fulfillment:
    - Same member
    - Same branch
    - Matching giving category
    - Pledge not yet fulfilled
    - Amount matches or exceeds pledge
    
    Strategy:
    - Prioritizes oldest unfulfilled pledges first
    - Can partially fulfill multiple pledges
    - Updates pledge.amount_fulfilled
    - Deactivates a pledge when amount_pledged == amount_fulfilled
    
    Called by:
    - Webhook processor (online giving)
    - Manual giving entry
    - Bulk giving import
    
    Args:
        giving: Giving instance
    
    Returns:
        list of (Pledge, amount_fulfilled) tuples
    """
    from django.db.models import F

    from .models import Pledge
    from decimal import Decimal
    
    if not giving.member:
        # Anonymous giving cannot be matched to pledges
        return []
    
    # Find unfulfilled pledges for this member
    unfulfilled_pledges = Pledge.objects.filter(
        member=giving.member,
        branch=giving.branch,
        category=giving.category,
        is_active=True,
        amount_fulfilled__lt=F("amount_pledged"),
    ).order_by('created_at')  # FIFO: fulfill oldest pledges first
    
    remaining_amount = giving.amount
    fulfilled = []
    
    for pledge in unfulfilled_pledges:
        if remaining_amount <= Decimal('0.00'):
            break
        
        # Calculate unfulfilled portion
        unfulfilled = pledge.amount_pledged - (pledge.amount_fulfilled or Decimal('0.00'))
        
        if unfulfilled <= Decimal('0.00'):
            # Pledge already fulfilled (shouldn't happen with status filter)
            continue
        
        # Determine how much to allocate to this pledge
        allocation = min(remaining_amount, unfulfilled)
        
        # Update pledge
        pledge.amount_fulfilled = (pledge.amount_fulfilled or Decimal('0.00')) + allocation
        
        # Check if pledge is now fully fulfilled
        if pledge.amount_fulfilled >= pledge.amount_pledged:
            pledge.is_active = False
        
        pledge.save()
        
        fulfilled.append((pledge, allocation))
        remaining_amount -= allocation
        
        payments_logger.info(
            "pledge_fulfilled pledge=%s giving=%s amount=%s currency=%s",
            pledge.id,
            giving.id,
            allocation,
            giving.currency,
        )
    
    return fulfilled
