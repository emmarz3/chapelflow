from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class LogoutTests(TestCase):
    def test_logout_clears_auth_cookies_without_server_error(self):
        user = User.objects.create_user(email="logout@example.edu", password="safe-password-123")
        client = APIClient()
        client.force_authenticate(user)

        response = client.post("/api/v1/auth/logout/", {"refresh": str(RefreshToken.for_user(user))})

        self.assertEqual(response.status_code, 200)
        for name in ("chapelflow_access", "chapelflow_refresh", "chapelflow_csrf"):
            self.assertIn(name, response.cookies)
            self.assertEqual(response.cookies[name].value, "")
