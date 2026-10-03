import uuid
from datetime import date

import pytest
from django.urls import reverse

from core.models import Department
from tests.test_views import GRID, HX, PANELS
from timetable.models import Resource, Subject, Timetable, Version


def make_timetable(name, department):
    return Timetable.objects.create(
        name=name,
        department=department,
        grid=GRID,
        start_date=date(2026, 1, 5),
        end_date=date(2026, 5, 30),
    )


@pytest.fixture
def other_department(scope):
    return Department.objects.create(name="ECE")


@pytest.fixture
def timetables(department, other_department):
    return {
        "own": make_timetable("CSE Sem 3", department),
        "other": make_timetable("ECE Sem 3", other_department),
        "shared": make_timetable("Common electives", None),
    }


def test_hod_sees_only_own_and_shared_timetables(as_hod, timetables):
    page = as_hod.get(reverse("panel-timetables"), headers=HX).content.decode()
    assert "CSE Sem 3" in page
    assert "Common electives" in page
    assert "ECE Sem 3" not in page


def test_hod_gets_404_for_other_department_timetable(as_hod, timetables):
    other = reverse("timetable-detail", kwargs={"pk": timetables["other"].pk})
    assert as_hod.get(other).status_code == 404
    own = reverse("timetable-detail", kwargs={"pk": timetables["own"].pk})
    assert as_hod.get(own).status_code == 200


def test_hod_cannot_archive_shared_timetable(as_hod, timetables):
    shared = timetables["shared"]
    response = as_hod.post(reverse("timetable-archive", kwargs={"pk": shared.pk}))
    assert response.status_code == 404
    shared.refresh_from_db()
    assert shared.archived is False


def test_hod_cannot_touch_other_department_version(as_hod, timetables):
    version = Version.objects.create(timetable=timetables["other"], number=1, grid=GRID)
    assert as_hod.get(reverse("version-detail", kwargs={"pk": version.pk})).status_code == 404
    assert as_hod.post(reverse("version-solve", kwargs={"pk": version.pk})).status_code == 404


def test_hod_gets_404_editing_shared_resource(as_hod, department):
    shared = Resource.objects.create(kind="room", code="R1", capacity=40)
    own = Resource.objects.create(kind="teacher", code="T1", max_load=10, department=department)
    shared_edit = reverse("resource-edit", kwargs={"pk": shared.pk})
    assert as_hod.get(shared_edit, headers=HX).status_code == 404
    assert (
        as_hod.post(shared_edit, {"kind": "room", "code": "R1", "capacity": "1"}).status_code == 404
    )
    assert as_hod.post(reverse("resource-toggle", kwargs={"pk": shared.pk})).status_code == 404
    assert (
        as_hod.get(reverse("resource-edit", kwargs={"pk": own.pk}), headers=HX).status_code == 200
    )
    listing = as_hod.get(reverse("panel-resources"), {"kind": "room"}, headers=HX).content.decode()
    assert "R1" in listing


def test_hod_department_field_is_pinned_to_own_department(as_hod, department, other_department):
    response = as_hod.post(
        reverse("subject-create"),
        {
            "code": "EC101",
            "name": "Circuits",
            "length": "1",
            "department": str(other_department.pk),
        },
        headers=HX,
    )
    assert response.status_code == 200
    assert not Subject.objects.filter(code="EC101").exists()
    response = as_hod.post(
        reverse("subject-create"),
        {"code": "CS101", "name": "Programming", "length": "1", "department": str(department.pk)},
        headers=HX,
    )
    assert response.status_code == 200
    assert Subject.objects.get(code="CS101").department == department


def test_hod_cannot_edit_shared_subject(as_hod):
    shared = Subject.objects.create(code="HS101", name="Ethics")
    assert as_hod.get(reverse("subject-edit", kwargs={"pk": shared.pk})).status_code == 404
    assert as_hod.post(reverse("subject-toggle", kwargs={"pk": shared.pk})).status_code == 404


def test_hod_forbidden_on_users_and_roles(as_hod):
    assert as_hod.get(reverse("panel-users")).status_code == 403
    assert as_hod.get(reverse("panel-roles")).status_code == 403
    assert as_hod.post(reverse("user-invite"), {"email": "x@gehu.test"}).status_code == 403


def test_hod_root_redirects_to_timetables(as_hod):
    response = as_hod.get("/")
    assert response.status_code == 302
    assert response["Location"] == reverse("panel-timetables")


def protected_urls():
    pk = uuid.uuid4()
    resource = uuid.uuid4()
    names = [
        ("admin", {}),
        ("my-timetable", {}),
        ("timetable-create", {}),
        ("timetable-detail", {"pk": pk}),
        ("timetable-archive", {"pk": pk}),
        ("version-create", {"pk": pk}),
        ("version-detail", {"pk": pk}),
        ("requirement-add", {"pk": pk}),
        ("requirement-edit", {"pk": pk}),
        ("requirement-delete", {"pk": pk}),
        ("version-solve", {"pk": pk}),
        ("version-status", {"pk": pk}),
        ("version-reopen", {"pk": pk}),
        ("version-publish", {"pk": pk}),
        ("version-compare", {"pk": pk}),
        ("version-grid-section", {"pk": pk, "resource": resource}),
        ("version-grid-teacher", {"pk": pk, "resource": resource}),
        ("version-grid-room", {"pk": pk, "resource": resource}),
        ("resource-create", {}),
        ("resource-edit", {"pk": pk}),
        ("resource-toggle", {"pk": pk}),
        ("subject-create", {}),
        ("subject-edit", {"pk": pk}),
        ("subject-toggle", {"pk": pk}),
        ("data-import", {}),
        ("data-export", {}),
        ("user-invite", {}),
        ("user-toggle", {"pk": pk}),
        ("user-resend", {"pk": pk}),
        ("user-reset-mfa", {"pk": pk}),
        ("role-create", {}),
        ("role-edit", {"pk": pk}),
        ("role-delete", {"pk": pk}),
    ] + [(f"panel-{panel}", {}) for panel in PANELS]
    return names


@pytest.mark.parametrize(
    ("name", "kwargs"), protected_urls(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_anonymous_is_redirected_to_login(client, tenant, name, kwargs):
    url = reverse(name, kwargs=kwargs)
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))
    assert "next=" in response["Location"]
