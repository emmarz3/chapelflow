import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

WAITLIST_MESSAGE = (
    "Your request has been processed. For new registrations, Scendey may send "
    "an email verification message. Existing registrations are not duplicated."
)


class ScendeyWaitlistSignupSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    audienceCategory = serializers.ChoiceField(
        choices=("student", "staff", "business", "other")
    )
    brandName = serializers.CharField(
        min_length=2, max_length=100, trim_whitespace=True, required=False
    )
    category = serializers.CharField(
        min_length=1, max_length=60, trim_whitespace=True, required=False
    )
    marketingConsent = serializers.BooleanField(required=False, default=False)
    website = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        if attrs["audienceCategory"] == "business":
            if not attrs.get("brandName") or not attrs.get("category"):
                raise serializers.ValidationError({
                    "brandName": "Enter your business or brand name.",
                    "category": "Choose a business category.",
                })
        return attrs


class ScendeyWaitlistSignupView(APIView):
    """Relay public waitlist submissions to Scendey without exposing provider access."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scendey_waitlist"

    def post(self, request):
        raw = request.data if isinstance(request.data, dict) else {}
        # Quietly discard bot submissions. Return the same public response as a
        # successful request so the honeypot does not expose its detection.
        if str(raw.get("website") or "").strip():
            return Response({"data": {"processed": True, "message": WAITLIST_MESSAGE}})

        serializer = ScendeyWaitlistSignupSerializer(data=raw)
        if not serializer.is_valid():
            return Response(
                {
                    "message": "Check the highlighted fields and try again.",
                    "fieldErrors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        endpoint = str(getattr(settings, "SCENDEY_WAITLIST_URL", "") or "").strip()
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            logger.warning("scendey_waitlist_endpoint_not_configured_or_invalid")
            return Response(
                {"message": "Waitlist registration is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        data = serializer.validated_data
        audience = data["audienceCategory"]
        is_business = audience == "business"
        payload = {
            "role": "BRAND" if is_business else "SHOPPER",
            "audienceCategory": audience.upper(),
            "name": data["name"],
            "email": data["email"],
            "consent": data["marketingConsent"],
            "source": "ChapelFlow",
        }
        if is_business:
            payload.update({
                "brandName": data["brandName"],
                "category": data["category"],
            })

        try:
            provider_response = requests.post(
                endpoint,
                json=payload,
                headers={"Accept": "application/json"},
                timeout=(3, 12),
            )
        except requests.RequestException:
            logger.warning("scendey_waitlist_provider_unreachable")
            return Response(
                {"message": "Scendey could not be reached. Please try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if provider_response.status_code == 429:
            return Response(
                {"message": "Waitlist registration is busy. Please try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
                headers={"Retry-After": provider_response.headers.get("Retry-After", "60")},
            )

        try:
            provider_data = provider_response.json()
        except ValueError:
            provider_data = {}

        if not provider_response.ok or provider_data.get("ok") is not True:
            logger.warning(
                "scendey_waitlist_provider_rejected_submission status=%s",
                provider_response.status_code,
            )
            return Response(
                {"message": "Scendey could not process this registration. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Do not reveal whether an email already exists. Scendey enforces the
        # unique-email rule and remains the only source of truth for entries.
        return Response({
            "data": {
                "processed": True,
                "message": WAITLIST_MESSAGE,
            }
        }, status=status.HTTP_200_OK)
