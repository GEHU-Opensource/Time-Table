import threading
from datetime import date, timedelta

import pytest
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from core.models import AuditEvent, Role, Tenant, User
from core.perms import ROLE_PRESETS
from core.tenancy import tenant_scope
from tests.test_services import (
    GRID,
    add_requirement,
    blocked_violations,
    make_timetable,
    occupy,
    room,
    section,
    solved_draft,
    subject,
    teacher,
    world,
)
from timetable import bridge, services
from timetable.models import Assignment, Requirement, Version

__all__ = ["world"]


def today():
    return timezone.localdate()


def clashing_draft(world, name="ECE Odd", grid=GRID):
    other = make_timetable(name, world["actor"], grid=grid)
    draft = services.create_draft(other, actor=world["actor"])
    req = add_requirement(draft, world["phys"], [world["t1"]], [world["s2"]])
    occupy(draft, req, 0, 0, 0, [world["r2"]])
    return draft


def test_publish_today_flips_live(world, django_capture_on_commit_callbacks):
    version = solved_draft(world)
    with django_capture_on_commit_callbacks(execute=True):
        published = services.publish(version, effective_from=today(), actor=world["actor"])
    assert published.status == Version.Status.PUBLISHED
    assert published.effective_from == today()
    assert published.published_at is not None
    rows = Assignment.objects.filter(version=published)
    assert rows.exists() and not rows.filter(is_live=False).exists()
    event = AuditEvent.objects.get(action="version.published")
    assert event.after["live"] is True
    assert mail.outbox == []


def test_publish_emails_teachers_with_users(world, roles, django_capture_on_commit_callbacks):
    user = User.objects.create_user("t1@gehu.test", "Teacher One", role=roles["Faculty"])
    world["t1"].user = user
    world["t1"].save()
    version = solved_draft(world)
    with django_capture_on_commit_callbacks(execute=True):
        services.publish(version, effective_from=today(), actor=world["actor"])
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["t1@gehu.test"]
    assert "CSE Odd" in message.body
    assert "Mon 09:00-09:55: MATH in R1" in message.body
    assert "Tue 11:00-11:55: MATH in R1" in message.body
    assert "PHYS" not in message.body
    assert "Teacher One" not in message.body
    assert "Admin" not in message.body


def test_publish_rejects_bad_states_and_dates(world):
    empty = services.create_draft(world["timetable"], actor=world["actor"])
    with pytest.raises(services.ServiceError):
        services.publish(empty, effective_from=today(), actor=world["actor"])
    version = solved_draft(world)
    with pytest.raises(services.ServiceError):
        services.publish(version, effective_from=today() - timedelta(days=1), actor=world["actor"])
    with pytest.raises(services.ServiceError):
        services.publish(version, effective_from=date(2031, 1, 1), actor=world["actor"])
    services.publish(version, effective_from=today(), actor=world["actor"])
    with pytest.raises(services.NotDraft):
        services.publish(version, effective_from=today(), actor=world["actor"])
    second = services.create_draft(world["timetable"], parent=version, actor=world["actor"])
    copies = {r.subject.code: r for r in second.requirements.select_related("subject")}
    occupy(second, copies["MATH"], 0, 0, 0, [world["r1"]])
    with pytest.raises(services.ServiceError):
        services.publish(second, effective_from=today(), actor=world["actor"])
    future = today() + timedelta(days=7)
    published = services.publish(second, effective_from=future, actor=world["actor"])
    assert published.status == Version.Status.PUBLISHED


def test_future_publish_waits_for_flip_live(world):
    version = solved_draft(world)
    future = today() + timedelta(days=3)
    published = services.publish(version, effective_from=future, actor=world["actor"])
    assert not Assignment.objects.filter(version=published, is_live=True).exists()
    services.flip_live(today())
    assert not Assignment.objects.filter(version=published, is_live=True).exists()
    services.flip_live(future)
    rows = Assignment.objects.filter(version=published)
    assert not rows.filter(is_live=False).exists()
    assert AuditEvent.objects.filter(action="version.went_live", object_id=published.pk).exists()
    services.flip_live(future)
    assert AuditEvent.objects.filter(action="version.went_live").count() == 1


def test_flip_live_retires_older_version(world):
    first = solved_draft(world)
    services.publish(first, effective_from=today(), actor=world["actor"])
    second = services.create_draft(world["timetable"], parent=first, actor=world["actor"])
    copies = {r.subject.code: r for r in second.requirements.select_related("subject")}
    occupy(second, copies["MATH"], 0, 1, 0, [world["r1"]])
    future = today() + timedelta(days=1)
    services.publish(second, effective_from=future, actor=world["actor"])
    assert Assignment.objects.filter(version=first, is_live=True).exists()
    services.flip_live(future)
    assert not Assignment.objects.filter(version=first, is_live=True).exists()
    assert not Assignment.objects.filter(version=second, is_live=False).exists()


def test_clash_with_live_teacher_is_caught_by_validator(world, monkeypatch):
    monkeypatch.setattr(bridge, "validate_placements", blocked_violations)
    services.publish(solved_draft(world), effective_from=today(), actor=world["actor"])
    draft = clashing_draft(world)
    with pytest.raises(services.Conflict) as caught:
        services.publish(draft, effective_from=today(), actor=world["actor"])
    assert any(str(world["t1"].pk) in violation for violation in caught.value.violations)
    draft.refresh_from_db()
    assert draft.status == Version.Status.DRAFT


def test_live_index_rejects_clash_when_validator_is_blind(world):
    services.publish(solved_draft(world), effective_from=today(), actor=world["actor"])
    draft = clashing_draft(world)
    with pytest.raises(services.Conflict) as caught:
        services.publish(draft, effective_from=today(), actor=world["actor"])
    assert caught.value.violations[0].startswith("live slot clash")
    draft.refresh_from_db()
    assert draft.status == Version.Status.DRAFT
    assert not Assignment.objects.filter(version=draft, is_live=True).exists()


def test_published_requirements_are_frozen(world):
    version = solved_draft(world)
    services.publish(version, effective_from=today(), actor=world["actor"])
    with pytest.raises(IntegrityError), transaction.atomic():
        Requirement.objects.filter(pk=world["req_math"].pk).update(sessions=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        world["req_math"].participants.all().delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        add_requirement(version, world["math"], [world["t2"]], [world["s2"]])
    with pytest.raises(IntegrityError), transaction.atomic():
        Version.objects.filter(pk=version.pk).update(reason="edited")


def test_versions_cannot_be_deleted(world):
    with pytest.raises(IntegrityError), transaction.atomic():
        Version.objects.filter(pk=world["draft"].pk).delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        world["timetable"].delete()


@pytest.mark.django_db(transaction=True)
def test_concurrent_publish_lets_exactly_one_win(monkeypatch):
    monkeypatch.setattr(bridge, "validate_placements", lambda instance, placements: [])
    monkeypatch.setattr(bridge, "precheck_instance", lambda instance: [])
    tenant = Tenant.objects.create(name="GEHU", slug="gehu")
    with tenant_scope(tenant.id):
        role = Role.objects.create(name="Admin", permissions=list(ROLE_PRESETS["Admin"]))
        actor = User.objects.create_user("admin@gehu.test", "Admin", role=role)
        shared = teacher("T1")
        r1, r2 = room("R1"), room("R2")
        s1, s2 = section("S1"), section("S2")
        math = subject("MATH")
        drafts = []
        for name, sec, rm in (("A", s1, r1), ("B", s2, r2)):
            draft = services.create_draft(make_timetable(name, actor), actor=actor)
            req = add_requirement(draft, math, [shared], [sec])
            occupy(draft, req, 0, 0, 0, [rm])
            drafts.append(draft)

    outcomes = {}
    barrier = threading.Barrier(2)

    def attempt(index, draft):
        try:
            barrier.wait(timeout=10)
            with tenant_scope(tenant.id):
                services.publish(draft, effective_from=today(), actor=actor)
            outcomes[index] = "published"
        except services.Conflict:
            outcomes[index] = "conflict"
        except Exception as exc:
            outcomes[index] = f"error: {exc!r}"
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt, args=(i, d)) for i, d in enumerate(drafts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes.values()) == ["conflict", "published"]
    with tenant_scope(tenant.id):
        assert Version.objects.filter(status=Version.Status.PUBLISHED).count() == 1
        assert Assignment.objects.filter(is_live=True, resource=shared).count() == 1
