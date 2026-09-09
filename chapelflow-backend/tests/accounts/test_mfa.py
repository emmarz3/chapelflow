import pytest
from django.test import override_settings


@pytest.mark.django_db
class TestMFAEnrollment:
    def test_enroll_returns_secret_and_provisioning_uri(self, api_client, branch_a):
        from apps.accounts.models import User

        user = User.objects.create_user(email="mfa1@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/v1/auth/mfa/enroll/")
        assert response.status_code == 200
        data = response.data["data"]
        assert data["secret"]
        assert data["provisioning_uri"].startswith("otpauth://totp/")
        assert "qr_code_base64" in data  # present even if None when qrcode isn't installed

        from apps.accounts.models import MFADevice
        device = MFADevice.objects.get(user=user)
        assert device.secret == data["secret"]
        assert device.confirmed is False

    def test_re_enrolling_issues_a_new_secret_and_resets_confirmation(self, api_client, branch_a):
        from apps.accounts.models import MFADevice, User

        user = User.objects.create_user(email="mfa2@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)

        first = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
        MFADevice.objects.filter(user=user).update(confirmed=True)

        second = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
        assert first != second

        device = MFADevice.objects.get(user=user)
        assert device.confirmed is False


@pytest.mark.django_db
class TestMFAConfirmation:
    def test_confirm_with_valid_totp_enables_mfa(self, api_client, branch_a):
        import pyotp

        from apps.accounts.models import User

        user = User.objects.create_user(email="mfa3@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)

        secret = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
        otp = pyotp.TOTP(secret).now()

        response = api_client.post("/api/v1/auth/mfa/confirm/", {"otp": otp})
        assert response.status_code == 200
        assert response.data["data"]["mfa_enabled"] is True

        user.refresh_from_db()
        assert user.mfa_enabled is True

        from apps.accounts.models import MFADevice
        assert MFADevice.objects.get(user=user).confirmed is True

    def test_confirm_with_wrong_code_fails_and_does_not_enable_mfa(self, api_client, branch_a):
        from apps.accounts.models import User

        user = User.objects.create_user(email="mfa4@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)
        api_client.post("/api/v1/auth/mfa/enroll/")

        response = api_client.post("/api/v1/auth/mfa/confirm/", {"otp": "000000"})
        assert response.status_code == 400

        user.refresh_from_db()
        assert user.mfa_enabled is False

    def test_confirm_rejects_malformed_otp(self, api_client, branch_a):
        from apps.accounts.models import User

        user = User.objects.create_user(email="mfa5@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)
        api_client.post("/api/v1/auth/mfa/enroll/")

        response = api_client.post("/api/v1/auth/mfa/confirm/", {"otp": "abc"})
        assert response.status_code == 400

    def test_confirm_without_prior_enrollment_fails_cleanly(self, api_client, branch_a):
        from apps.accounts.models import User

        user = User.objects.create_user(email="mfa6@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_a)
        api_client.force_authenticate(user=user)

        response = api_client.post("/api/v1/auth/mfa/confirm/", {"otp": "123456"})
        assert response.status_code == 400


@pytest.mark.django_db
class TestMFAEnforcement:
    """
    Spec section 18: users whose role is in MFA_ENFORCED_ROLES must
    complete MFA setup before using any RBAC-protected endpoint. Test
    settings turn MFA_ENFORCED_ROLES off by default (see
    config/settings/test.py) so this is exercised explicitly per-test via
    override_settings, rather than affecting every fixture-created admin
    elsewhere in the suite.
    """

    @override_settings(MFA_ENFORCED_ROLES=["CHAPEL_ADMIN"])
    def test_enforced_role_without_mfa_is_blocked_from_protected_endpoints(
        self, api_client, chapel_admin_a, seed_member_permissions
    ):
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 403

    @override_settings(MFA_ENFORCED_ROLES=["CHAPEL_ADMIN"])
    def test_enforced_role_can_still_reach_enroll_and_confirm_while_blocked(
        self, api_client, chapel_admin_a
    ):
        import pyotp

        api_client.force_authenticate(user=chapel_admin_a)
        # Blocked from an RBAC-protected endpoint...
        assert api_client.get("/api/v1/members/").status_code == 403
        # ...but MFA setup itself (IsAuthenticated only) is never blocked.
        secret = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
        otp = pyotp.TOTP(secret).now()
        assert api_client.post("/api/v1/auth/mfa/confirm/", {"otp": otp}).status_code == 200

    @override_settings(MFA_ENFORCED_ROLES=["CHAPEL_ADMIN"])
    def test_enforced_role_regains_access_after_completing_mfa(
        self, api_client, chapel_admin_a, seed_member_permissions
    ):
        import pyotp

        api_client.force_authenticate(user=chapel_admin_a)
        secret = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
        otp = pyotp.TOTP(secret).now()
        api_client.post("/api/v1/auth/mfa/confirm/", {"otp": otp})

        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200

    @override_settings(MFA_ENFORCED_ROLES=["CHAPEL_ADMIN"])
    def test_super_admin_is_not_exempt_from_mfa_enforcement_when_listed(self, api_client, super_admin):
        """
        Even though Super Admin bypasses ordinary role/permission-code
        checks, it must NOT bypass a completed-MFA requirement if its role
        is explicitly listed in MFA_ENFORCED_ROLES.
        """
        with override_settings(MFA_ENFORCED_ROLES=["SUPER_ADMIN"]):
            api_client.force_authenticate(user=super_admin)
            response = api_client.get("/api/v1/members/")
            assert response.status_code == 403

    def test_role_not_in_enforced_list_is_unaffected(self, api_client, chapel_admin_a, seed_member_permissions):
        # MFA_ENFORCED_ROLES is [] in test settings by default -> nobody is blocked.
        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/members/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestAdministrativeMFAReset:
    """
    Spec section 18/administrative remediation: Chapel Admin or Super
    Admin can reset a user's MFA when their authenticator is lost.
    """

    def _enrolled_user(self, branch, email="locked@test.com"):
        import pyotp

        from apps.accounts.models import MFADevice, User

        user = User.objects.create_user(email=email, password="Pass12345!", role="CHAPEL_ADMIN", branch=branch)
        device = MFADevice.objects.create(user=user, secret=pyotp.random_base32(), confirmed=True)
        user.mfa_enabled = True
        user.save(update_fields=["mfa_enabled"])
        return user, device

    def test_chapel_admin_can_reset_a_users_mfa_in_their_own_branch(self, api_client, branch_a, chapel_admin_a):
        target, device = self._enrolled_user(branch_a, email="locked1@test.com")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id), "reason": "Lost phone"})
        assert response.status_code == 200
        assert response.data["data"]["mfa_enabled"] is False

        target.refresh_from_db()
        device.refresh_from_db()
        assert target.mfa_enabled is False
        assert device.confirmed is False

    def test_super_admin_can_reset_mfa_across_branches(self, api_client, branch_a, super_admin):
        target, device = self._enrolled_user(branch_a, email="locked2@test.com")

        api_client.force_authenticate(user=super_admin)
        response = api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id)})
        assert response.status_code == 200

        device.refresh_from_db()
        assert device.confirmed is False

    def test_chapel_admin_cannot_reset_mfa_in_another_branch(self, api_client, branch_a, branch_b):
        from apps.accounts.models import User

        admin_b = User.objects.create_user(email="admin-b@test.com", password="Pass12345!", role="CHAPEL_ADMIN", branch=branch_b)
        target, device = self._enrolled_user(branch_a, email="locked3@test.com")

        api_client.force_authenticate(user=admin_b)
        response = api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id)})
        assert response.status_code == 404  # fails closed, doesn't confirm the user's existence

        device.refresh_from_db()
        assert device.confirmed is True  # unchanged

    def test_member_cannot_reset_anyones_mfa(self, api_client, branch_a, member_in_branch_a):
        target, device = self._enrolled_user(branch_a, email="locked4@test.com")
        from apps.accounts.models import User

        member_user = User.objects.create_user(email="plainmember@test.com", password="Pass12345!", role="MEMBER", branch=branch_a)

        api_client.force_authenticate(user=member_user)
        response = api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id)})
        assert response.status_code == 403

    def test_reset_writes_an_audit_log_entry(self, api_client, branch_a, chapel_admin_a):
        target, device = self._enrolled_user(branch_a, email="locked5@test.com")

        api_client.force_authenticate(user=chapel_admin_a)
        api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id), "reason": "Lost device"})

        from apps.audit.models import AuditLog
        assert AuditLog.objects.filter(action="MFA_RESET", resource_id=str(target.id)).exists()

    def test_reset_user_can_re_enroll_and_regain_access(self, api_client, branch_a, chapel_admin_a, seed_member_permissions):
        """Full loop: enrolled -> admin reset -> user re-enrolls -> confirms -> works again."""
        import pyotp
        from django.test import override_settings

        target, device = self._enrolled_user(branch_a, email="locked6@test.com")

        api_client.force_authenticate(user=chapel_admin_a)
        api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(target.id)})

        # Refresh: `target` is a plain Python object created before the
        # reset endpoint touched the DB via a separate query. Django's
        # OneToOne reverse descriptor (user.mfa_device) caches on first
        # access — and object creation caches it too — so re-authenticating
        # with this exact stale object would silently use its cached,
        # pre-reset MFADevice. Real HTTP requests never hit this (each
        # request re-fetches the user), so this is purely a test-harness
        # artifact of reusing one Python object across force_authenticate
        # calls, not something the endpoint itself needs to guard against.
        target.refresh_from_db()

        api_client.force_authenticate(user=target)
        with override_settings(MFA_ENFORCED_ROLES=["CHAPEL_ADMIN"]):
            # Blocked immediately after reset.
            assert api_client.get("/api/v1/members/").status_code == 403

            new_secret = api_client.post("/api/v1/auth/mfa/enroll/").data["data"]["secret"]
            otp = pyotp.TOTP(new_secret).now()
            confirm = api_client.post("/api/v1/auth/mfa/confirm/", {"otp": otp})
            assert confirm.status_code == 200

            target.refresh_from_db()
            assert target.mfa_enabled is True

    def test_reset_nonexistent_user_returns_404(self, api_client, chapel_admin_a):
        import uuid

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.post("/api/v1/auth/mfa/reset/", {"user_id": str(uuid.uuid4())})
        assert response.status_code == 404
