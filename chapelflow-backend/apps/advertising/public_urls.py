from django.urls import path

from .scendey import ScendeyWaitlistSignupView

urlpatterns = [
    path("scendey-waitlist/", ScendeyWaitlistSignupView.as_view(), name="scendey-waitlist-signup"),
]
