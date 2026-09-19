"""
Phase 14: Finance reconciliation Celery tasks.
"""
import json
import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import OperationalError, transaction
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def auto_reconcile_branch_transactions(self, branch_id):
    """
    Phase 14: Reconcile previous day's transactions for a specific branch.
    
    Daily task:
    - Compares gateway payments with internal giving records
    - Detects matches, mismatches, and orphans
    - Creates reconciliation alerts for discrepancies
    
    Args:
        branch_id: UUID of branch to reconcile
    
    Returns:
    {
        "branch_id": str,
        "period_start": str,
        "period_end": str,
        "summary": {...},
        "alerts_created": int
    }
    """
    from apps.organizations.models import Branch
    from .models import Reconciliation
    from .services import reconcile_gateway_transactions

    # Reconcile previous day
    yesterday = timezone.localdate() - timedelta(days=1)
    period_start = datetime.combine(yesterday, time.min)
    period_end = datetime.combine(yesterday, time.max)

    # Make timezone-aware
    period_start = timezone.make_aware(period_start)
    period_end = timezone.make_aware(period_end)

    with transaction.atomic():
        try:
            # A branch row is a stable, existing lock target. Holding it for the
            # whole transaction serializes this branch's daily reconciliation
            # across workers, including the idempotency check and alert writes.
            branch = Branch.objects.select_for_update().get(id=branch_id)
        except Branch.DoesNotExist:
            logger.error("auto_reconcile_branch_transactions: Branch %s not found", branch_id)
            return {"error": "Branch not found"}

        existing = Reconciliation.objects.filter(
            branch=branch,
            period_start=yesterday,
            period_end=yesterday,
        ).first()
        if existing:
            logger.info(
                "auto_reconcile_branch_transactions: branch=%s date=%s already processed",
                branch.id,
                yesterday,
            )
            return _existing_reconciliation_response(existing)

        result = reconcile_gateway_transactions(
            branch=branch,
            period_start=period_start,
            period_end=period_end,
        )
        reconciliation = _persist_reconciliation(branch, yesterday, result)

        alerts_created = 0
        if result["unmatched_payments"] or result["unmatched_giving"] or result["mismatches"]:
            alerts_created = create_reconciliation_alerts(
                branch=branch,
                period_start=period_start,
                period_end=period_end,
                result=result,
            )

        response = {
            "branch_id": str(branch_id),
            "branch_name": branch.name,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "reconciliation_id": str(reconciliation.id),
            "summary": result["summary"],
            "alerts_created": alerts_created,
            "already_processed": False,
        }

    logger.info(
        "auto_reconcile_branch_transactions: branch=%s, matched=%s, "
        "mismatches=%s, unmatched_payments=%s, alerts_created=%s",
        branch.name,
        result["summary"]["matched_count"],
        result["summary"]["mismatch_count"],
        result["summary"]["unmatched_payment_count"],
        alerts_created,
    )

    return response


def _persist_reconciliation(branch, reconciliation_date, result):
    from .models import (
        Reconciliation,
        ReconciliationResult,
        ReconciliationResultType,
        ReconciliationStatus,
    )

    bank_total = sum((payment.amount for payment, _giving in result["matched"]), Decimal("0"))
    bank_total += sum((payment.amount for payment in result["unmatched_payments"]), Decimal("0"))
    bank_total += sum(
        (payment.amount for payment, _giving, _diffs in result["mismatches"]),
        Decimal("0"),
    )
    system_total = sum((giving.amount for _payment, giving in result["matched"]), Decimal("0"))
    system_total += sum((giving.amount for giving in result["unmatched_giving"]), Decimal("0"))
    system_total += sum(
        (giving.amount for _payment, giving, _diffs in result["mismatches"]),
        Decimal("0"),
    )
    has_discrepancy = bool(
        result["unmatched_payments"] or result["unmatched_giving"] or result["mismatches"]
    )

    reconciliation = Reconciliation.objects.create(
        branch=branch,
        period_start=reconciliation_date,
        period_end=reconciliation_date,
        status=(
            ReconciliationStatus.DISCREPANCY
            if has_discrepancy
            else ReconciliationStatus.RECONCILED
        ),
        system_total=system_total,
        bank_total=bank_total,
        created_by=None,
        reconciled_at=timezone.now(),
    )

    rows = []
    for payment, giving in result["matched"]:
        rows.append(
            ReconciliationResult(
                reconciliation=reconciliation,
                result_type=ReconciliationResultType.MATCHED,
                payment=payment,
                giving=giving,
                expected_amount=giving.amount,
                actual_amount=payment.amount,
                difference=giving.amount - payment.amount,
            )
        )
    for payment in result["unmatched_payments"]:
        rows.append(
            ReconciliationResult(
                reconciliation=reconciliation,
                result_type=ReconciliationResultType.UNMATCHED_PAYMENT,
                payment=payment,
                actual_amount=payment.amount,
            )
        )
    for giving in result["unmatched_giving"]:
        rows.append(
            ReconciliationResult(
                reconciliation=reconciliation,
                result_type=ReconciliationResultType.UNMATCHED_GIVING,
                giving=giving,
                expected_amount=giving.amount,
            )
        )
    for payment, giving, differences in result["mismatches"]:
        rows.append(
            ReconciliationResult(
                reconciliation=reconciliation,
                result_type=ReconciliationResultType.AMOUNT_MISMATCH,
                payment=payment,
                giving=giving,
                expected_amount=giving.amount,
                actual_amount=payment.amount,
                difference=giving.amount - payment.amount,
                notes=json.dumps(differences, sort_keys=True),
            )
        )

    ReconciliationResult.objects.bulk_create(rows)
    return reconciliation


def _existing_reconciliation_response(reconciliation):
    from .models import ReconciliationResultType

    period_start = timezone.make_aware(datetime.combine(reconciliation.period_start, time.min))
    period_end = timezone.make_aware(datetime.combine(reconciliation.period_end, time.max))
    counts = {
        row["result_type"]: row["count"]
        for row in reconciliation.results.values("result_type").annotate(count=Count("id"))
    }
    summary = {
        "total_payments": (
            counts.get(ReconciliationResultType.MATCHED, 0)
            + counts.get(ReconciliationResultType.UNMATCHED_PAYMENT, 0)
            + counts.get(ReconciliationResultType.AMOUNT_MISMATCH, 0)
        ),
        "total_giving": (
            counts.get(ReconciliationResultType.MATCHED, 0)
            + counts.get(ReconciliationResultType.UNMATCHED_GIVING, 0)
            + counts.get(ReconciliationResultType.AMOUNT_MISMATCH, 0)
        ),
        "matched_count": counts.get(ReconciliationResultType.MATCHED, 0),
        "mismatch_count": counts.get(ReconciliationResultType.AMOUNT_MISMATCH, 0),
        "unmatched_payment_count": counts.get(ReconciliationResultType.UNMATCHED_PAYMENT, 0),
        "unmatched_giving_count": counts.get(ReconciliationResultType.UNMATCHED_GIVING, 0),
    }
    return {
        "branch_id": str(reconciliation.branch_id),
        "branch_name": reconciliation.branch.name,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "reconciliation_id": str(reconciliation.id),
        "summary": summary,
        "alerts_created": 0,
        "already_processed": True,
    }


@shared_task
def reconcile_all_branches():
    """
    Phase 14: Reconcile all branches (daily trigger).
    
    Runs daily via CELERY_BEAT_SCHEDULE:
    - Triggers reconciliation for each active branch
    - Runs as separate tasks for parallelization
    
    Returns:
    {
        "branches_processed": int,
        "tasks_dispatched": int
    }
    """
    from apps.organizations.models import Branch
    
    branches = Branch.objects.all()
    
    dispatched = 0
    for branch in branches:
        auto_reconcile_branch_transactions.delay(str(branch.id))
        dispatched += 1
    
    logger.info(f"reconcile_all_branches: dispatched {dispatched} reconciliation tasks")
    
    return {
        "branches_processed": branches.count(),
        "tasks_dispatched": dispatched
    }


def create_reconciliation_alerts(branch, period_start, period_end, result):
    """
    Create reconciliation alerts for discrepancies.
    
    Sends notifications to finance team about:
    - Unmatched payments (gateway shows payment, no giving record)
    - Unmatched giving (giving record exists, no payment)
    - Mismatches (linked but amounts/members don't match)
    
    Returns:
        int: Number of alerts created
    """
    from apps.notifications.models import Notification
    from apps.notifications.tasks import deliver_notification
    from django.contrib.auth import get_user_model
    from common.constants.roles import Roles
    
    User = get_user_model()
    
    # Find finance staff to notify
    finance_staff = User.objects.filter(
        branch=branch,
        role__in=Roles.FINANCE_ACCESS_ROLES
    )
    
    if not finance_staff.exists():
        logger.warning(f"No finance staff found for branch {branch.id} to send reconciliation alerts")
        return 0
    
    alerts_created = 0
    
    # Build alert message
    summary = result['summary']
    message_lines = [
        f"Reconciliation Alert for {branch.name}",
        f"Period: {period_start.date()} to {period_end.date()}",
        "",
        f"Matched: {summary['matched_count']}",
        f"Mismatches: {summary['mismatch_count']}",
        f"Unmatched Payments: {summary['unmatched_payment_count']}",
        f"Unmatched Giving: {summary['unmatched_giving_count']}",
    ]
    
    if result['mismatches']:
        message_lines.append("")
        message_lines.append("Mismatches found:")
        for payment, giving, differences in result['mismatches'][:5]:  # First 5
            message_lines.append(
                f"- Payment {payment.provider_reference}: {', '.join(d['field'] for d in differences)}"
            )
    
    alert_body = "\n".join(message_lines)
    
    # Send to all finance staff
    for staff in finance_staff:
        notification, created = Notification.objects.get_or_create(
            recipient=staff,
            title=f"Reconciliation Alert - {branch.name}",
            body=alert_body,
            channel="EMAIL",
        )
        if created:
            transaction.on_commit(
                lambda notification_id=str(notification.id): deliver_notification.delay(notification_id)
            )
            alerts_created += 1
    
    return alerts_created
