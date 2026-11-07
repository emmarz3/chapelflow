from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FinancialDashboardView, FinancialStatementViewSet, GivingCategoryViewSet, GivingViewSet,
    MemberGivingHistoryView, MemberGivingSummaryView, MemberPledgeHistoryView,
    PaystackCheckoutInitializeView, PaystackCheckoutVerifyView,
    PaymentViewSet, PaymentWebhookView, PledgeViewSet,
    ReconciliationViewSet, RefundViewSet,
)

router = DefaultRouter()
router.register("giving", GivingViewSet, basename="giving")
router.register("giving-categories", GivingCategoryViewSet, basename="giving-category")
router.register("pledges", PledgeViewSet, basename="pledge")
router.register("payments", PaymentViewSet, basename="payment")
router.register("statements", FinancialStatementViewSet, basename="statement")
router.register("reconciliations", ReconciliationViewSet, basename="reconciliation")
router.register("refunds", RefundViewSet, basename="refund")

urlpatterns = [
    path("giving/checkout/", PaystackCheckoutInitializeView.as_view(), name="paystack-checkout"),
    path("giving/checkout/verify/", PaystackCheckoutVerifyView.as_view(), name="paystack-checkout-verify"),
    path("payments/webhook/<str:provider>/", PaymentWebhookView.as_view(), name="payment-webhook"),
    path("me/giving/", MemberGivingHistoryView.as_view(), name="member-giving-history"),
    path("me/giving/summary/", MemberGivingSummaryView.as_view(), name="member-giving-summary"),
    path("me/pledges/", MemberPledgeHistoryView.as_view(), name="member-pledge-history"),
    path("dashboard/", FinancialDashboardView.as_view(), name="financial-dashboard"),
] + router.urls
