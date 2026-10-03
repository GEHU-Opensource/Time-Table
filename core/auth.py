from django.contrib.auth.backends import BaseBackend

from core.models import User
from core.tenancy import TenantUnset

BACKEND_PATH = "core.auth.TenantBackend"


class TenantBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = (
                User.objects.filter(email=username.lower(), is_active=True)
                .select_related("role")
                .first()
            )
        except TenantUnset:
            user = None
        if user is None:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", False)

    def get_user(self, user_id):
        try:
            user = User.objects.filter(pk=user_id).select_related("role").first()
        except TenantUnset:
            return None
        if user is None or not self.user_can_authenticate(user):
            return None
        return user
