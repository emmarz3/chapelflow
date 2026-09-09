"""
Phase 14: Finance reconciliation Celery tasks.
"""
import logging
from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def auto_reconcile_branch_transactions(branch_id):
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
    from .services import reconcile_gateway_transactions
    
    try:
        branch = Branch.objects.get(id=branch_id)
    except Branch.DoesNotExist:
        logger.error(f"auto_reconcile_branch_transactions: Branch {branch_id} not found")
        return {"error": "Branch not found"}
    
    # Reconcile previous day
    yesterday = timezone.now().date() - timedelta(days=1)
    period_start = datetime.combine(yesterday, time.min)
    period_end = datetime.combine(yesterday, time.max)
    
    # Make timezone-aware
    period_start = timezone.make_aware(period_start)
    period_end = timezone.make_aware(period_end)
    
    # Run reconciliation
    result = reconcile_gateway_transactions(
        branch=branch,
        period_start=period_start,
        period_end=period_end
    )
    
    alerts_created = 0
    
    # Create alerts for issues
    if result['unmatched_payments'] or result['mismatches']:
        alerts_created = create_reconciliation_alerts(
            branch=branch,
            period_start=period_start,
            period_end=period_end,
            result=result
        )
    
    logger.info(
        f"auto_reconcile_branch_transactions: branch={branch.name}, "
        f"matched={result['summary']['matched_count']}, "
        f"mismatches={result['summary']['mismatch_count']}, "
        f"unmatched_payments={result['summary']['unmatched_payment_count']}, "
        f"alerts_created={alerts_created}"
    )
    
    return {
        "branch_id": str(branch_id),
        "branch_name": branch.name,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "summary": result['summary'],
        "alerts_created": alerts_created
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
        notification = Notification.objects.create(
            recipient=staff,
            title=f"Reconciliation Alert - {branch.name}",
            body=alert_body,
            channel="EMAIL"
        )
        deliver_notification.delay(str(notification.id))
        alerts_created += 1
    
    return alerts_created
