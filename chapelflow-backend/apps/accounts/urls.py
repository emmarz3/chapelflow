from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("setup/super-admin/", views.LocalSuperAdminSetupView.as_view(), name="auth-super-admin-setup"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path("profile/", views.StudentProfileView.as_view(), name="auth-student-profile"),
    path("profile/photo/", views.ProfilePhotoUploadView.as_view(), name="auth-profile-photo-upload"),
    path("mfa/enroll/", views.MFAEnrollView.as_view(), name="auth-mfa-enroll"),
    path("mfa/confirm/", views.MFAConfirmView.as_view(), name="auth-mfa-confirm"),
    path("mfa/reset/", views.MFAResetView.as_view(), name="auth-mfa-reset"),
    path("password-reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("sessions/", views.SessionListView.as_view(), name="auth-sessions"),
    path("sessions/revoke/", views.SessionRevokeView.as_view(), name="auth-sessions-revoke"),
    path("sessions/revoke-all/", views.SessionRevokeAllView.as_view(), name="auth-sessions-revoke-all"),
    path("permissions/", views.PermissionListCreateView.as_view(), name="auth-permissions"),
    path("roles/", views.RoleListView.as_view(), name="auth-roles"),
    path("roles/<str:role>/permissions/", views.RolePermissionView.as_view(), name="auth-role-permissions"),
    path("institutional-accounts/", views.InstitutionalAccountListCreateView.as_view(), name="institutional-accounts"),
    path("institutional-accounts/<uuid:pk>/", views.InstitutionalAccountDetailView.as_view(), name="institutional-account-detail"),
    path("institutional-accounts/<uuid:pk>/password-reset/", views.InstitutionalAccountPasswordResetView.as_view(), name="institutional-account-password-reset"),
]
