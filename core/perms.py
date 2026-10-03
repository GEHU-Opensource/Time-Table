from enum import StrEnum

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.shortcuts import redirect
from django.views.generic import TemplateView


class Perm(StrEnum):
    RESOURCE_VIEW = "resource.view"
    RESOURCE_MANAGE = "resource.manage"
    SUBJECT_MANAGE = "subject.manage"
    TIMETABLE_VIEW = "timetable.view"
    TIMETABLE_MANAGE = "timetable.manage"
    TIMETABLE_GENERATE = "timetable.generate"
    TIMETABLE_PUBLISH = "timetable.publish"
    DATA_IMPORT = "data.import"
    DATA_EXPORT = "data.export"
    USER_MANAGE = "user.manage"
    ROLE_MANAGE = "role.manage"
    TENANT_SETTINGS = "tenant.settings"


PRIVILEGED = frozenset(
    {Perm.TIMETABLE_PUBLISH, Perm.USER_MANAGE, Perm.ROLE_MANAGE, Perm.TENANT_SETTINGS}
)

ROLE_PRESETS = {
    "Admin": [p.value for p in Perm],
    "HOD": [
        Perm.RESOURCE_VIEW.value,
        Perm.RESOURCE_MANAGE.value,
        Perm.SUBJECT_MANAGE.value,
        Perm.TIMETABLE_VIEW.value,
        Perm.TIMETABLE_MANAGE.value,
        Perm.TIMETABLE_GENERATE.value,
        Perm.DATA_IMPORT.value,
        Perm.DATA_EXPORT.value,
    ],
    "Faculty": [Perm.TIMETABLE_VIEW.value],
}


def can(user, perm, obj=None, write=False):
    if not user.is_authenticated or perm not in user.perms:
        return False
    if obj is None or user.department_id is None:
        return True
    department_id = getattr(obj, "department_id", None)
    if department_id == user.department_id:
        return True
    return department_id is None and not write


def mfa_redirect(user):
    from django_otp import user_has_device

    if not user.needs_mfa or user.is_verified():
        return None
    return redirect("mfa-verify" if user_has_device(user, confirmed=True) else "mfa-setup")


class PermissionedView(TemplateView):
    permission = None

    def dispatch(self, request, *args, **kwargs):
        from django.contrib.auth.views import redirect_to_login

        if self.permission is None:
            raise ImproperlyConfigured(f"{type(self).__name__} declares no permission")
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        blocked = mfa_redirect(request.user)
        if blocked is not None:
            return blocked
        if not can(request.user, self.permission):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
