"""
Provider abstraction: business logic (tasks.py) never calls a specific
vendor SDK directly. Swapping providers means adding a class here and
changing settings — nothing else in the codebase changes.
"""
import logging

from django.conf import settings

logger = logging.getLogger("chapelflow.audit")


class EmailProvider:
    def send(self, *, to: str, subject: str, body: str):
        from django.core.mail import send_mail
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        return {"status": "sent"}


class SMSProvider:
    """Termii (settings.SMS_PROVIDER == 'termii'). Falls back to the
    stubbed response when no SMS_API_KEY is configured, so nothing
    breaks in dev/test/CI where that env var is intentionally unset —
    see tests/communications/test_delivery_states.py, which asserts SMS
    stays STUBBED rather than SENT in exactly that situation.
    """

    def send(self, *, to: str, body: str):
        if not settings.SMS_API_KEY:
            logger.info("sms_stub_send to=%s provider=%s", to, settings.SMS_PROVIDER)
            return {"status": "stubbed", "provider": settings.SMS_PROVIDER}

        if settings.SMS_PROVIDER == "termii":
            return self._send_termii(to=to, body=body)

        logger.warning("sms_unknown_provider provider=%s", settings.SMS_PROVIDER)
        return {"status": "stubbed", "provider": settings.SMS_PROVIDER}

    def _send_termii(self, *, to: str, body: str):
        import requests

        try:
            response = requests.post(
                "https://api.ng.termii.com/api/sms/send",
                json={
                    "to": to,
                    "from": settings.SMS_SENDER_ID,
                    "sms": body,
                    "type": "plain",
                    "channel": "generic",
                    "api_key": settings.SMS_API_KEY,
                },
                timeout=15,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("sms_termii_send_failed to=%s error=%s", to, exc)
            return {"status": "failed", "provider": "termii", "error": str(exc)}

        # Termii returns HTTP 200 with a message_id on success; error
        # responses vary (missing/invalid sender ID, insufficient
        # balance, etc.) but consistently omit message_id.
        if response.status_code == 200 and data.get("message_id"):
            return {"status": "sent", "provider": "termii", "message_id": data["message_id"]}

        logger.error("sms_termii_send_rejected to=%s response=%s", to, data)
        return {"status": "failed", "provider": "termii", "error": data}


class PushProvider:
    """Firebase Cloud Messaging v1 API. Falls back to the stubbed
    response when no FIREBASE_SERVICE_ACCOUNT_JSON is configured, same
    pattern as SMSProvider — see test_delivery_states.py, which asserts
    PUSH stays STUBBED when unconfigured.
    """

    def send(self, *, device_token: str, title: str, body: str):
        if not settings.FIREBASE_SERVICE_ACCOUNT_JSON:
            logger.info("push_stub_send device_token=%s", device_token)
            return {"status": "stubbed"}

        if not device_token:
            return {"status": "failed", "provider": "fcm", "error": "no device_token"}

        try:
            access_token = self._get_access_token()
        except Exception as exc:
            logger.error("push_fcm_auth_failed error=%s", exc)
            return {"status": "failed", "provider": "fcm", "error": f"auth: {exc}"}

        import requests

        project_id = settings.FIREBASE_PROJECT_ID
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        payload = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
            }
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error("push_fcm_send_failed device_token=%s error=%s", device_token, exc)
            return {"status": "failed", "provider": "fcm", "error": str(exc)}

        if response.status_code == 200:
            return {"status": "sent", "provider": "fcm", "message_id": response.json().get("name")}

        logger.error("push_fcm_send_rejected device_token=%s status=%s body=%s",
                      device_token, response.status_code, response.text)
        return {"status": "failed", "provider": "fcm", "error": response.text}

    def _get_access_token(self) -> str:
        """Cached on the class so we're not re-parsing the service
        account JSON and hitting Google's token endpoint on every send —
        google-auth handles refresh once the cached token nears expiry.
        """
        import json

        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        if getattr(PushProvider, "_credentials", None) is None:
            info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
            PushProvider._credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/firebase.messaging"]
            )
        credentials = PushProvider._credentials
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token


email_provider = EmailProvider()
sms_provider = SMSProvider()
push_provider = PushProvider()
