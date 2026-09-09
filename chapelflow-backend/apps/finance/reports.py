"""
Phase 8: Financial reporting services.

All reports are scope-aware and pre-filter data before aggregation
to prevent information leakage.
"""
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import Giving, GivingStatus, Payment, PaymentStatus, Pledge


def giving_summary_by_category(branch, start_date=None, end_date=None):
    """
    Calculate giving totals by category for a specific branch.
    
    Security: Pre-filtered by branch before aggregation.
    
    Args:
        branch: Branch instance
        start_date: Optional start date filter
        end_date: Optional end date filter
    
    Returns:
        List of dicts with category name and total amount
    """
    qs = Giving.objects.filter(
        branch=branch,
        status=GivingStatus.CONFIRMED  # Only confirmed transactions
    )
    
    if start_date:
        qs = qs.filter(given_at__gte=start_date)
    if end_date:
        qs = qs.filter(given_at__lte=end_date)
    
    return list(
        qs.values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )


def giving_summary_by_source(branch, start_date=None, end_date=None):
    """
    Calculate giving totals by source (ONLINE/OFFLINE/etc) for a branch.
    
    Security: Pre-filtered by branch.
    """
    qs = Giving.objects.filter(
        branch=branch,
        status=GivingStatus.CONFIRMED
    )
    
    if start_date:
        qs = qs.filter(given_at__gte=start_date)
    if end_date:
        qs = qs.filter(given_at__lte=end_date)
    
    return list(
        qs.values('source')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )


def giving_summary_by_event(branch, start_date=None, end_date=None):
    """
    Phase 8: Calculate event-specific contributions.
    
    Security: Pre-filtered by branch.
    """
    qs = Giving.objects.filter(
        branch=branch,
        status=GivingStatus.CONFIRMED,
        event__isnull=False  # Only event-specific giving
    )
    
    if start_date:
        qs = qs.filter(given_at__gte=start_date)
    if end_date:
        qs = qs.filter(given_at__lte=end_date)
    
    return list(
        qs.values('event__id', 'event__name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )


def giving_summary_by_group(branch, start_date=None, end_date=None):
    """
    Phase 8: Calculate group/fellowship/unit-specific contributions.
    
    Security: Pre-filtered by branch.
    """
    qs = Giving.objects.filter(
        branch=branch,
        status=GivingStatus.CONFIRMED,
        group__isnull=False  # Only group-specific giving
    )
    
    if start_date:
        qs = qs.filter(given_at__gte=start_date)
    if end_date:
        qs = qs.filter(given_at__lte=end_date)
    
    return list(
        qs.values('group__id', 'group__name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )


def payment_status_summary(branch, start_date=None, end_date=None):
    """
    Calculate payment gateway transaction status summary.
    
    Security: Pre-filtered by branch.
    """
    qs = Payment.objects.filter(branch=branch)
    
    if start_date:
        qs = qs.filter(created_at__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__lte=end_date)
    
    return list(
        qs.values('status')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('status')
    )


def pledge_fulfillment_summary(branch):
    """
    Calculate pledge fulfillment statistics.
    
    Security: Pre-filtered by branch.
    """
    pledges = Pledge.objects.filter(
        branch=branch,
        is_active=True
    )
    
    total_pledged = pledges.aggregate(total=Sum('amount_pledged'))['total'] or Decimal('0')
    total_fulfilled = pledges.aggregate(total=Sum('amount_fulfilled'))['total'] or Decimal('0')
    
    return {
        'total_pledged': total_pledged,
        'total_fulfilled': total_fulfilled,
        'total_remaining': total_pledged - total_fulfilled,
        'fulfillment_rate': (total_fulfilled / total_pledged * 100) if total_pledged > 0 else Decimal('0'),
        'active_pledge_count': pledges.count()
    }


def member_giving_summary(member):
    """
    Calculate giving summary for a specific member (self-service).
    
    Security: Only returns data for the specified member.
    
    Returns:
        Dict with total, count, by_category breakdown
    """
    giving = Giving.objects.filter(
        member=member,
        status=GivingStatus.CONFIRMED
    )
    
    total = giving.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    count = giving.count()
    
    by_category = list(
        giving.values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    
    return {
        'total_amount': total,
        'transaction_count': count,
        'by_category': by_category,
        'first_giving': giving.order_by('given_at').first(),
        'latest_giving': giving.order_by('-given_at').first(),
    }


def branch_financial_dashboard(branch, start_date=None, end_date=None):
    """
    Complete financial dashboard for a branch.
    
    Security: All queries pre-filtered by branch before aggregation.
    
    Args:
        branch: Branch instance
        start_date: Optional period start
        end_date: Optional period end
    
    Returns:
        Dict with comprehensive financial metrics
    """
    # Default to current month if no dates provided
    if not start_date:
        start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not end_date:
        end_date = timezone.now()
    
    giving_qs = Giving.objects.filter(
        branch=branch,
        status=GivingStatus.CONFIRMED,
        given_at__gte=start_date,
        given_at__lte=end_date
    )
    
    payment_qs = Payment.objects.filter(
        branch=branch,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    return {
        'period_start': start_date,
        'period_end': end_date,
        'total_giving': giving_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        'giving_count': giving_qs.count(),
        'by_category': list(
            giving_qs.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        ),
        'by_source': list(
            giving_qs.values('source')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        ),
        'payment_successful': payment_qs.filter(
            status=PaymentStatus.SUCCESSFUL
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        'payment_pending': payment_qs.filter(
            status=PaymentStatus.PENDING
        ).count(),
        'payment_failed': payment_qs.filter(
            status=PaymentStatus.FAILED
        ).count(),
        'unique_contributors': giving_qs.filter(
            member__isnull=False
        ).values('member').distinct().count(),
        'pledge_summary': pledge_fulfillment_summary(branch),
    }
