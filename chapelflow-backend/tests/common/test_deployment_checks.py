from django.test import override_settings

from common.checks import (
    check_allowed_hosts_not_default,
    check_email_configured,
    check_payment_provider_configured,
    check_sms_provider_configured,
    check_storage_provider_credentials,
)


class TestDeploymentChecks:
    """
    These call the check functions directly rather than shelling out to
    `manage.py check --deploy`, so each case can flip exactly the
    setting(s) it cares about with override_settings.
    """

    def test_allowed_hosts_still_dev_default_warns(self):
        with override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1"]):
            findings = check_allowed_hosts_not_default(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W001"

    def test_allowed_hosts_customized_is_clean(self):
        with override_settings(ALLOWED_HOSTS=["chapelflow.example.edu"]):
            findings = check_allowed_hosts_not_default(None)
        assert findings == []

    def test_cloudinary_missing_credentials_warns(self):
        with override_settings(
            STORAGE_PROVIDER="cloudinary",
            CLOUDINARY_CLOUD_NAME="", CLOUDINARY_API_KEY="", CLOUDINARY_API_SECRET="",
        ):
            findings = check_storage_provider_credentials(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W002"
        assert "CLOUDINARY_CLOUD_NAME" in findings[0].msg

    def test_cloudinary_with_all_credentials_is_clean(self):
        with override_settings(
            STORAGE_PROVIDER="cloudinary",
            CLOUDINARY_CLOUD_NAME="demo", CLOUDINARY_API_KEY="key", CLOUDINARY_API_SECRET="secret",
        ):
            findings = check_storage_provider_credentials(None)
        assert findings == []

    def test_s3_missing_credentials_warns(self):
        with override_settings(
            STORAGE_PROVIDER="s3",
            AWS_ACCESS_KEY_ID="", AWS_SECRET_ACCESS_KEY="", AWS_STORAGE_BUCKET_NAME="",
        ):
            findings = check_storage_provider_credentials(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W002"

    def test_local_storage_warns_about_persistence(self):
        with override_settings(STORAGE_PROVIDER="local"):
            findings = check_storage_provider_credentials(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W003"

    def test_email_host_blank_warns(self):
        with override_settings(EMAIL_HOST=""):
            findings = check_email_configured(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W004"

    def test_email_host_set_is_clean(self):
        with override_settings(EMAIL_HOST="smtp.example.com"):
            findings = check_email_configured(None)
        assert findings == []

    def test_no_payment_provider_warns(self):
        with override_settings(PAYSTACK_SECRET_KEY="", FLUTTERWAVE_SECRET_KEY=""):
            findings = check_payment_provider_configured(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W005"

    def test_one_payment_provider_configured_is_clean(self):
        with override_settings(PAYSTACK_SECRET_KEY="sk_live_x", FLUTTERWAVE_SECRET_KEY=""):
            findings = check_payment_provider_configured(None)
        assert findings == []

    def test_sms_key_blank_warns(self):
        with override_settings(SMS_API_KEY=""):
            findings = check_sms_provider_configured(None)
        assert len(findings) == 1
        assert findings[0].id == "chapelflow.W006"
