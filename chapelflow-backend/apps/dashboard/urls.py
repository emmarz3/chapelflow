from django.urls import path

from .views import (
    AdminDashboardView,
    ExecutiveDashboardView,
    FinanceDashboardView,
    MemberDashboardView,
    MinistryLeaderDashboardView,
    PastorDashboardView,
    RoleOperationsDashboardView,
)

urlpatterns = [
    path("admin/", AdminDashboardView.as_view(), name="dashboard-admin"),
    path("pastor/", PastorDashboardView.as_view(), name="dashboard-pastor"),
    path("finance/", FinanceDashboardView.as_view(), name="dashboard-finance"),
    path("member/", MemberDashboardView.as_view(), name="dashboard-member"),
    path("executive/", ExecutiveDashboardView.as_view(), name="dashboard-executive"),
    path("ministry/", MinistryLeaderDashboardView.as_view(), name="dashboard-ministry"),
    path("operations/", RoleOperationsDashboardView.as_view(), name="dashboard-operations"),
]
