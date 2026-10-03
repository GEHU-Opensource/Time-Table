from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import include, path, reverse

from core.models import Department
from core.perms import Perm, PermissionedView, can


class ManageProbeView(PermissionedView):
    permission = Perm.TIMETABLE_MANAGE

    def get(self, request, *args, **kwargs):
        return HttpResponse("manage probe")


class ViewProbeView(PermissionedView):
    permission = Perm.TIMETABLE_VIEW

    def get(self, request, *args, **kwargs):
        return HttpResponse("view probe")


class UnconfiguredView(PermissionedView):
    pass


urlpatterns = [
    path("", include("config.urls")),
    path("probe/manage/", ManageProbeView.as_view(), name="probe-manage"),
    path("probe/view/", ViewProbeView.as_view(), name="probe-view"),
]

handler403 = "core.views.forbidden"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_perms")]


def test_can_matrix_with_department_scoping(admin_user, hod_user, faculty_user, department):
    other_department = Department.objects.create(name="ECE")
    own = SimpleNamespace(department_id=department.id)
    shared = SimpleNamespace(department_id=None)
    foreign = SimpleNamespace(department_id=other_department.id)

    assert can(admin_user, Perm.RESOURCE_MANAGE)
    assert can(admin_user, Perm.RESOURCE_MANAGE, foreign, write=True)
    assert can(admin_user, Perm.RESOURCE_MANAGE, shared, write=True)

    assert can(hod_user, Perm.RESOURCE_MANAGE, own, write=True)
    assert can(hod_user, Perm.RESOURCE_VIEW, own)
    assert can(hod_user, Perm.RESOURCE_VIEW, shared)
    assert not can(hod_user, Perm.RESOURCE_MANAGE, shared, write=True)
    assert not can(hod_user, Perm.RESOURCE_VIEW, foreign)
    assert not can(hod_user, Perm.RESOURCE_MANAGE, foreign, write=True)
    assert not can(hod_user, Perm.USER_MANAGE)
    assert not can(hod_user, Perm.TIMETABLE_PUBLISH, own)

    assert can(faculty_user, Perm.TIMETABLE_VIEW)
    assert can(faculty_user, Perm.TIMETABLE_VIEW, foreign)
    assert not can(faculty_user, Perm.RESOURCE_VIEW)
    assert not can(faculty_user, Perm.TIMETABLE_MANAGE, shared, write=True)

    assert not can(AnonymousUser(), Perm.TIMETABLE_VIEW)


def test_user_without_role_has_no_permissions(roles):
    from core.models import User

    user = User.objects.create_user("norole@gehu.test", "No Role")
    assert user.perms == frozenset()
    assert not user.needs_mfa
    assert not can(user, Perm.TIMETABLE_VIEW)


def test_view_without_permission_is_misconfigured(tenant):
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    with pytest.raises(ImproperlyConfigured):
        UnconfiguredView.as_view()(request)


def test_anonymous_is_redirected_to_login(client, tenant):
    response = client.get(reverse("probe-view"))
    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={reverse('probe-view')}"


def test_missing_permission_gives_403(as_faculty):
    response = as_faculty.get(reverse("probe-manage"))
    assert response.status_code == 403
    assert b"Not allowed" in response.content


def test_hod_with_manage_permission_serves_page(as_hod):
    assert as_hod.get(reverse("probe-manage")).status_code == 200


def test_faculty_with_view_permission_serves_page(as_faculty):
    assert as_faculty.get(reverse("probe-view")).status_code == 200


def test_admin_with_verified_device_serves_page(as_admin):
    assert as_admin.get(reverse("probe-manage")).status_code == 200
