from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import User
from .validators import normalize_matric_no


class MatricOrEmailBackend(ModelBackend):
    """
    Students/members authenticate with matric_no + password.
    Staff/admins authenticate with email + password.
    The `username` kwarg accepts either identifier transparently.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("matric_no") or kwargs.get("email")
        if identifier is None or password is None:
            return None

        normalized_matric = normalize_matric_no(identifier)

        try:
            user = User.objects.get(Q(email__iexact=identifier) | Q(matric_no=normalized_matric))
        except User.DoesNotExist:
            User().set_password(password)  # mitigate timing attacks
            return None
        except User.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
