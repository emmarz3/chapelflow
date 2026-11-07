from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.utils import timezone

from apps.finance.models import (
    Giving,
    GivingCategory,
    GivingSource,
    Payment,
    PaymentStatus,
    Reconciliation,
    ReconciliationResult,
)
from apps.notifications.models import Notification
from apps.finance.tasks import (
    auto_reconcile_branch_transactions,
    create_reconciliation_alerts,
)
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles


User = get_user_model()


@pytest.fixture
def branch():
    organization = Organization.objects.create(name="Task Test Org", slug="task-test-org")
    return Branch.objects.create(name="Task Test Branch", organization=organization)


@pytest.fixture
def matched_result(branch):
    yesterday = timezone.now() - timedelta(days=1)
    payment = Payment.objects.create(
        branch=branch,
        provider="PAYSTACK",
        provider_reference="task-test-payment",
        amount=Decimal("250.00"),
        status=PaymentStatus.SUCCESSFUL,
        confirmed_at=yesterday,
    )
    giving = Giving.objects.create(
        branch=branch,
        category=GivingCategory.objects.create(name="Task Test Offering"),
        amount=Decimal("250.00"),
        source=GivingSource.ONLINE,
        payment=payment,
        given_at=yesterday,
    )
    return {
        "matched": [(payment, giving)],
        "unmatched_payments": [],
        "unmatched_giving": [],
        "mismatches": [],
        "summary": {
            "total_payments": 1,
            "total_giving": 1,
            "matched_count": 1,
            "mismatch_count": 0,
            "unmatched_payment_count": 0,
            "unmatched_giving_count": 0,
        },
    }


@pytest.mark.django_db
def test_reconciliation_task_is_idempotent_and_locks_branch(branch, matched_result):
    with (
        patch(
            "apps.finance.services.reconcile_gateway_transactions",
            return_value=matched_result,
        ) as reconcile,
        patch.object(
            Branch.objects,
            "select_for_update",
            wraps=Branch.objects.select_for_update,
        ) as select_for_update,
    ):
        first = auto_reconcile_branch_transactions.run(str(branch.id))
        second = auto_reconcile_branch_transactions.run(str(branch.id))

    assert first["already_processed"] is False
    assert second["already_processed"] is True
    assert reconcile.call_count == 1
    assert select_for_update.call_count == 2
    assert Reconciliation.objects.count() == 1
    assert ReconciliationResult.objects.count() == 1


@pytest.mark.django_db
def test_reconciliation_alert_creation_is_idempotent(branch):
    User.objects.create_user(
        email="finance-task@example.com",
        password="StrongPassword123!",
        role=Roles.FINANCE_OFFICER,
        branch=branch,
    )
    period = timezone.now() - timedelta(days=1)
    result = {
        "matched": [],
        "unmatched_payments": [object()],
        "unmatched_giving": [],
        "mismatches": [],
        "summary": {
            "matched_count": 0,
            "mismatch_count": 0,
            "unmatched_payment_count": 1,
            "unmatched_giving_count": 0,
        },
    }

    with patch("apps.notifications.tasks.deliver_notification.delay"):
        assert create_reconciliation_alerts(branch, period, period, result) == 1
        assert create_reconciliation_alerts(branch, period, period, result) == 0

    assert Notification.objects.count() == 1


def test_reconciliation_task_retries_transient_database_errors():
    assert auto_reconcile_branch_transactions.autoretry_for
    assert auto_reconcile_branch_transactions.retry_backoff is True
    assert auto_reconcile_branch_transactions.max_retries == 5


@pytest.mark.django_db
def test_transient_failure_retries_and_rolls_back(branch, matched_result):
    failed_result = {
        **matched_result,
        "matched": [],
        "unmatched_payments": [matched_result["matched"][0][0]],
        "summary": {
            **matched_result["summary"],
            "matched_count": 0,
            "unmatched_payment_count": 1,
        },
    }

    with (
        patch(
            "apps.finance.services.reconcile_gateway_transactions",
            return_value=failed_result,
        ),
        patch(
            "apps.finance.tasks.create_reconciliation_alerts",
            side_effect=OperationalError("temporary database failure"),
        ),
        patch.object(
            auto_reconcile_branch_transactions,
            "retry",
            side_effect=Retry("retry scheduled"),
        ) as retry,
        pytest.raises(Retry),
    ):
        auto_reconcile_branch_transactions.run(str(branch.id))

    retry.assert_called_once()
    assert Reconciliation.objects.count() == 0
    assert ReconciliationResult.objects.count() == 0
