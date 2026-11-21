from datetime import date
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core import invites as invites_module
from timetable import excel as excel_module
from timetable import services
from timetable.models import Requirement, Resource, Subject, Timetable, Version

HX = {"HX-Request": "true"}
PANELS = ["timetables", "resources", "subjects", "data", "users", "roles"]
GRID = {
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "periods": [["09:00", "10:00"], ["10:00", "11:00"], ["11:00", "12:00"], ["12:00", "13:00"]],
    "breaks_after": [1],
}


def panel_url(name):
    return reverse(f"panel-{name}")


def html(response):
    return response.content.decode()


@pytest.fixture
def timetable(scope, department):
    return Timetable.objects.create(
        name="CSE Sem 3",
        department=department,
        grid=GRID,
        start_date=date(2026, 1, 5),
        end_date=date(2026, 5, 30),
    )


@pytest.fixture
def version(timetable, admin_user):
    return Version.objects.create(timetable=timetable, number=1, grid=GRID, created_by=admin_user)


@pytest.fixture
def catalogue(scope, department):
    return SimpleNamespace(
        subject=Subject.objects.create(code="CS301", name="Algorithms", department=department),
        teacher=Resource.objects.create(
            kind="teacher", code="T1", name="Ada", max_load=20, department=department
        ),
        section=Resource.objects.create(
            kind="section", code="A", capacity=60, department=department
        ),
        room=Resource.objects.create(kind="room", code="R101", capacity=70),
    )


def test_admin_root_redirects_to_timetables(as_admin):
    response = as_admin.get("/")
    assert response.status_code == 302
    assert response["Location"] == panel_url("timetables")


@pytest.mark.parametrize("panel", PANELS)
def test_panel_full_page_and_fragment(as_admin, panel):
    full = as_admin.get(panel_url(panel))
    assert full.status_code == 200
    assert "<html" in html(full)
    assert 'id="panel"' in html(full)
    fragment = as_admin.get(panel_url(panel), headers=HX)
    assert fragment.status_code == 200
    assert "<html" not in html(fragment)
    assert reverse("mfa-setup") not in html(fragment)
    assert "<section" in html(fragment)
    restored = as_admin.get(panel_url(panel), headers={**HX, "HX-History-Restore-Request": "true"})
    assert "<html" in html(restored)


def test_create_timetable_through_form(as_admin, admin_user, department, monkeypatch):
    seen = {}

    def fake_create(*, name, department, grid, start_date, end_date, actor):
        seen.update(grid=grid, actor=actor)
        return Timetable.objects.create(
            name=name, department=department, grid=grid, start_date=start_date, end_date=end_date
        )

    monkeypatch.setattr(services, "create_timetable", fake_create)
    response = as_admin.post(
        reverse("timetable-create"),
        {
            "name": "ECE Sem 1",
            "department": str(department.pk),
            "days": ["Mon", "Tue", "Wed"],
            "periods": "09:00-10:00\n10:00-11:00\n11:00-12:00",
            "breaks_after": "2",
            "start_date": "2026-01-05",
            "end_date": "2026-05-30",
        },
    )
    draft = Version.objects.get(timetable__name="ECE Sem 1")
    assert draft.number == 1
    assert draft.created_by == admin_user
    assert response.status_code == 302
    assert response["Location"] == reverse("version-detail", kwargs={"pk": draft.pk})
    assert seen["grid"] == {
        "days": ["Mon", "Tue", "Wed"],
        "periods": [["09:00", "10:00"], ["10:00", "11:00"], ["11:00", "12:00"]],
        "breaks_after": [1],
    }
    assert seen["actor"] == admin_user
    listing = as_admin.get(panel_url("timetables"), headers=HX)
    assert "ECE Sem 1" in html(listing)
    assert 'class="badge draft"' in html(listing)


def test_create_timetable_rejects_bad_periods(as_admin, department, monkeypatch):
    monkeypatch.setattr(services, "create_timetable", lambda **kwargs: pytest.fail("called"))
    response = as_admin.post(
        reverse("timetable-create"),
        {
            "name": "Broken",
            "days": ["Mon"],
            "periods": "9-10",
            "start_date": "2026-01-05",
            "end_date": "2026-05-30",
        },
        headers=HX,
    )
    assert response.status_code == 200
    assert "is not HH:MM-HH:MM" in html(response)


def test_add_requirement(as_admin, version, catalogue):
    response = as_admin.post(
        reverse("requirement-add", kwargs={"pk": version.pk}),
        {
            "subject": str(catalogue.subject.pk),
            "teachers": [str(catalogue.teacher.pk)],
            "attendees": [str(catalogue.section.pk)],
            "sessions": "3",
            "length": "",
            "room_tag": "lab",
            "rooms_needed": "1",
            "fixed_room": str(catalogue.room.pk),
            "fixed_slots": "Tue 2, fri 1",
        },
        headers=HX,
    )
    assert response.status_code == 200
    requirement = Requirement.objects.get(version=version)
    assert requirement.subject == catalogue.subject
    assert requirement.sessions == 3
    assert requirement.length == catalogue.subject.length
    assert requirement.fixed_slots == [[1, 1], [4, 0]]
    roles = {p.resource.code: p.role for p in requirement.participants.select_related("resource")}
    assert roles == {"T1": "teacher", "A": "attendee", "R101": "fixed_room"}
    page = html(response)
    assert "CS301" in page
    assert "Tue 2, Fri 1" in page
    assert "Requirement added" in page


def test_add_requirement_rejects_unknown_slot(as_admin, version, catalogue):
    response = as_admin.post(
        reverse("requirement-add", kwargs={"pk": version.pk}),
        {
            "subject": str(catalogue.subject.pk),
            "teachers": [str(catalogue.teacher.pk)],
            "attendees": [str(catalogue.section.pk)],
            "sessions": "1",
            "rooms_needed": "1",
            "fixed_slots": "Sun 9",
        },
        headers=HX,
    )
    assert response.status_code == 200
    assert "unknown day" in html(response)
    assert not Requirement.objects.filter(version=version).exists()


def test_edit_and_delete_requirement(as_admin, version, catalogue):
    requirement = Requirement.objects.create(version=version, subject=catalogue.subject, sessions=2)
    version.assignments.create(
        requirement=requirement, session=0, resource=catalogue.teacher, day=0, period=0
    )
    edit_url = reverse("requirement-edit", kwargs={"pk": requirement.pk})
    page = as_admin.get(edit_url, headers=HX)
    assert page.status_code == 200
    assert "Edit requirement" in html(page)
    response = as_admin.post(
        edit_url,
        {
            "subject": str(catalogue.subject.pk),
            "teachers": [str(catalogue.teacher.pk)],
            "attendees": [str(catalogue.section.pk)],
            "sessions": "4",
            "rooms_needed": "0",
        },
        headers=HX,
    )
    assert response.status_code == 200
    requirement.refresh_from_db()
    assert requirement.sessions == 4
    assert not requirement.assignments.exists()
    response = as_admin.post(reverse("requirement-delete", kwargs={"pk": requirement.pk}))
    assert response.status_code == 302
    assert not Requirement.objects.filter(pk=requirement.pk).exists()


def test_generate_and_status_polls_only_while_solving(as_admin, version, admin_user, monkeypatch):
    calls = []

    def fake_start_solve(target, actor):
        calls.append((target.pk, actor.pk))
        Version.objects.filter(pk=target.pk).update(status="solving")

    monkeypatch.setattr(services, "start_solve", fake_start_solve)
    response = as_admin.post(reverse("version-solve", kwargs={"pk": version.pk}), headers=HX)
    assert response.status_code == 200
    assert calls == [(version.pk, admin_user.pk)]
    assert 'hx-trigger="every 3s"' in html(response)

    status_url = reverse("version-status", kwargs={"pk": version.pk})
    polling = as_admin.get(status_url, headers=HX)
    assert 'hx-trigger="every 3s"' in html(polling)
    assert status_url in html(polling)
    assert 'class="badge solving"' in html(polling)
    assert "HX-Refresh" not in polling

    Version.objects.filter(pk=version.pk).update(
        status="failed", solver_stats={"reasons": ["no room fits lab"], "unplaced": [["r1", 0]]}
    )
    failed = as_admin.get(status_url, headers=HX)
    assert failed["HX-Refresh"] == "true"
    assert "hx-trigger" not in html(failed)
    assert "no room fits lab" in html(failed)
    assert "Unplaced sessions: 1" in html(failed)


def test_version_page_flags_a_stale_timetable(as_admin, version, catalogue):
    requirement = Requirement.objects.create(version=version, subject=catalogue.subject, sessions=2)
    url = reverse("version-detail", kwargs={"pk": version.pk})
    publish_url = reverse("version-publish", kwargs={"pk": version.pk})
    version.assignments.create(
        requirement=requirement, session=0, resource=catalogue.section, day=0, period=0
    )
    stale = html(as_admin.get(url, headers=HX))
    assert "requirements changed" in stale
    assert publish_url not in stale
    version.assignments.create(
        requirement=requirement, session=1, resource=catalogue.section, day=1, period=0
    )
    ready = html(as_admin.get(url, headers=HX))
    assert "The timetable is ready" in ready
    assert publish_url in ready


def test_archive_toggle(as_admin, timetable):
    url = reverse("timetable-archive", kwargs={"pk": timetable.pk})
    response = as_admin.post(url, headers=HX)
    assert response.status_code == 200
    timetable.refresh_from_db()
    assert timetable.archived is True
    assert "Unarchive" in html(response)
    as_admin.post(url)
    timetable.refresh_from_db()
    assert timetable.archived is False


def test_publish_renders_conflict_violations(as_admin, version, monkeypatch):
    def fake_publish(target, *, effective_from, actor):
        raise services.Conflict(["x"])

    monkeypatch.setattr(services, "publish", fake_publish)
    response = as_admin.post(
        reverse("version-publish", kwargs={"pk": version.pk}),
        {"effective_from": "2026-02-01"},
        headers=HX,
    )
    assert response.status_code == 200
    assert "Publishing blocked" in html(response)
    assert "<li>x</li>" in html(response)


def test_publish_success_redirects(as_admin, version, admin_user, monkeypatch):
    seen = {}

    def fake_publish(target, *, effective_from, actor):
        seen.update(pk=target.pk, effective_from=effective_from, actor=actor)

    monkeypatch.setattr(services, "publish", fake_publish)
    response = as_admin.post(
        reverse("version-publish", kwargs={"pk": version.pk}), {"effective_from": "2026-02-01"}
    )
    assert response.status_code == 302
    assert seen == {"pk": version.pk, "effective_from": date(2026, 2, 1), "actor": admin_user}


def test_compare_renders_two_grids(as_admin, version, timetable, catalogue, monkeypatch):
    other = Version.objects.create(timetable=timetable, number=2, grid=GRID, parent=version)
    requirement = Requirement.objects.create(version=version, subject=catalogue.subject, sessions=1)
    for resource in (catalogue.teacher, catalogue.section):
        version.assignments.create(
            requirement=requirement, session=0, resource=resource, day=0, period=1
        )
    monkeypatch.setattr(services, "compare", lambda a, b: {"moved": 1, "added": 0})
    response = as_admin.get(
        reverse("version-compare", kwargs={"pk": version.pk}), {"other": str(other.pk)}, headers=HX
    )
    page = html(response)
    assert response.status_code == 200
    assert "Compare v1 with v2" in page
    assert "<th>moved</th>" in page
    assert page.count('class="slot changed"') == 2
    assert page.count("<table") == 3
    assert "CS301" in page


def test_grid_by_section(as_admin, version, catalogue):
    requirement = Requirement.objects.create(version=version, subject=catalogue.subject, sessions=1)
    for resource in (catalogue.teacher, catalogue.section, catalogue.room):
        version.assignments.create(
            requirement=requirement, session=0, resource=resource, day=2, period=3
        )
    url = reverse(
        "version-grid-section", kwargs={"pk": version.pk, "resource": catalogue.section.pk}
    )
    response = as_admin.get(url, headers=HX)
    page = html(response)
    assert response.status_code == 200
    assert "<strong>CS301</strong>" in page
    assert "<small>T1</small>" in page
    assert "<small>R101</small>" in page
    wrong_kind = reverse(
        "version-grid-room", kwargs={"pk": version.pk, "resource": catalogue.section.pk}
    )
    assert as_admin.get(wrong_kind).status_code == 404


def test_export_calls_excel(as_admin, version, monkeypatch):
    monkeypatch.setattr(excel_module, "export_version", lambda target: b"xlsx-bytes")
    response = as_admin.post(reverse("data-export"), {"version": str(version.pk)})
    assert response.status_code == 200
    assert response["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response["Content-Disposition"] == 'attachment; filename="timetable-v1.xlsx"'
    assert response.content == b"xlsx-bytes"


def test_sample_workbook_downloads_and_parses(as_admin):
    response = as_admin.get(reverse("data-sample"))
    assert response.status_code == 200
    assert response["Content-Disposition"] == 'attachment; filename="timetable-sample.xlsx"'
    assert excel_module.parse_workbook(response.content).errors == []


def test_import_dry_run_then_apply(as_admin, admin_user, monkeypatch):
    applied = []
    plan = SimpleNamespace(errors=[], summary={"teachers": 4, "rooms": 2}, rows=[])

    def apply(target, actor):
        applied.append((target, actor))
        return {"created": 6}

    monkeypatch.setattr(excel_module, "parse_workbook", lambda data: plan)
    monkeypatch.setattr(excel_module, "apply", apply)
    url = reverse("data-import")
    dry = as_admin.post(
        url,
        {"file": SimpleUploadedFile("sheet.xlsx", b"PK"), "dry_run": "on"},
        headers=HX,
    )
    assert dry.status_code == 200
    assert "Dry run" in html(dry)
    assert "<th>teachers</th>" in html(dry)
    assert applied == []
    real = as_admin.post(url, {"file": SimpleUploadedFile("sheet.xlsx", b"PK")}, headers=HX)
    assert real.status_code == 200
    assert "Import applied" in html(real)
    assert "<th>created</th>" in html(real)
    assert applied == [(plan, admin_user)]


def test_import_rejects_wrong_extension(as_admin, monkeypatch):
    monkeypatch.setattr(excel_module, "parse_workbook", lambda data: pytest.fail("parsed"))
    response = as_admin.post(
        reverse("data-import"), {"file": SimpleUploadedFile("sheet.csv", b"a,b")}, headers=HX
    )
    assert response.status_code == 200
    assert "Only .xlsx workbooks are accepted" in html(response)


def test_invite_calls_core_invites(as_admin, admin_user, roles, department, monkeypatch):
    seen = {}

    def invite_user(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(invites_module, "invite_user", invite_user)
    response = as_admin.post(
        reverse("user-invite"),
        {
            "email": "new@gehu.test",
            "name": "Newcomer",
            "role": str(roles["Faculty"].pk),
            "department": str(department.pk),
        },
    )
    assert response.status_code == 302
    assert seen == {
        "email": "new@gehu.test",
        "name": "Newcomer",
        "role": roles["Faculty"],
        "department": department,
        "actor": admin_user,
    }


def test_user_toggle_bumps_auth_version(as_admin, faculty_user):
    response = as_admin.post(reverse("user-toggle", kwargs={"pk": faculty_user.pk}), headers=HX)
    assert response.status_code == 200
    faculty_user.refresh_from_db()
    assert faculty_user.is_active is False
    assert faculty_user.auth_version == 2


def test_role_delete_blocked_while_assigned(as_admin, roles):
    response = as_admin.post(reverse("role-delete", kwargs={"pk": roles["Faculty"].pk}), headers=HX)
    assert response.status_code == 200
    assert "still assigned" not in html(response)
    assert "Role deleted" in html(response)
    busy = as_admin.post(reverse("role-delete", kwargs={"pk": roles["Admin"].pk}), headers=HX)
    assert "still assigned" in html(busy)


def test_resource_create_with_unavailable_grid(as_admin, department):
    response = as_admin.post(
        reverse("resource-create"),
        {
            "kind": "teacher",
            "code": "T9",
            "name": "Grace",
            "department": str(department.pk),
            "capacity": "0",
            "tags": "lab, senior",
            "max_load": "18",
            "unavailable": ["0-0", "2-3"],
        },
        headers=HX,
    )
    assert response.status_code == 200
    resource = Resource.objects.get(code="T9")
    assert resource.tags == ["lab", "senior"]
    assert resource.unavailable == [[0, 0], [2, 3]]
    assert 'value="0-0" checked' not in html(response)
    edit = as_admin.get(reverse("resource-edit", kwargs={"pk": resource.pk}), headers=HX)
    assert 'value="0-0" checked' in html(edit)


@pytest.mark.parametrize("panel", PANELS)
def test_faculty_panels_forbidden(as_faculty, panel):
    assert as_faculty.get(panel_url(panel)).status_code == 403


def test_faculty_root_goes_to_my_timetable(as_faculty):
    response = as_faculty.get("/")
    assert response.status_code == 302
    assert response["Location"] == reverse("my-timetable")


def test_faculty_my_timetable_empty_state(as_faculty):
    response = as_faculty.get(reverse("my-timetable"))
    assert response.status_code == 200
    assert "No teaching schedule is linked" in html(response)


def test_my_timetable_merges_active_versions(
    as_faculty, faculty_user, version, catalogue, monkeypatch
):
    catalogue.teacher.user = faculty_user
    catalogue.teacher.save()
    requirement = Requirement.objects.create(version=version, subject=catalogue.subject, sessions=1)
    for resource in (catalogue.teacher, catalogue.section):
        version.assignments.create(
            requirement=requirement, session=0, resource=resource, day=1, period=2
        )
    monkeypatch.setattr(services, "active_version", lambda timetable, on: version)
    response = as_faculty.get(reverse("my-timetable"))
    assert response.status_code == 200
    assert "<strong>CS301</strong>" in html(response)
    assert "<small>A</small>" in html(response)
