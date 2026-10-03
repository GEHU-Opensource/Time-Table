import re
from io import StringIO

import pytest
from django.core import mail
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from core.models import AuditEvent, Role, Tenant, User
from core.perms import ROLE_PRESETS
from core.tenancy import tenant_scope
from tests.conftest import HOST

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "orbit-lantern-quartz-91"
LINK = re.compile(r"https://(?P<host>[a-z0-9-]+\.testserver)(?P<path>/invite/[A-Za-z0-9_-]+/)")


def run(command, **options):
    out = StringIO()
    call_command(command, stdout=out, **options)
    return out.getvalue()


def test_create_tenant_then_seed_admin_produces_a_working_invite(db):
    output = run("create_tenant", name="Test University", slug="TU")
    tenant = Tenant.objects.get(slug="tu")
    assert tenant.name == "Test University"
    assert str(tenant.id) in output
    with tenant_scope(tenant.id):
        assert set(Role.objects.values_list("name", flat=True)) == set(ROLE_PRESETS)
        assert sorted(Role.objects.get(name="Admin").permissions) == sorted(ROLE_PRESETS["Admin"])
        assert AuditEvent.objects.filter(action="tenant.created", object_id=tenant.id).exists()

    output = run(
        "seed_tenant_admin", tenant="tu", email="Admin@TU.test", name="Admin", print_link=True
    )
    match = LINK.search(output)
    assert match is not None
    assert match.group("host") == "tu.testserver"
    assert mail.outbox == []
    with tenant_scope(tenant.id):
        admin = User.objects.get(email="admin@tu.test")
        assert admin.role.name == "Admin"
        assert not admin.has_usable_password()
        assert AuditEvent.objects.filter(action="user.invited", object_id=admin.id).exists()

    client = Client(headers={"Host": match.group("host")})
    response = client.get(match.group("path"))
    assert response.status_code == 302
    response = client.post(
        reverse("invite-set-password"),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(admin.pk)
    with tenant_scope(tenant.id):
        admin.refresh_from_db()
        assert admin.check_password(NEW_PASSWORD)
        assert admin.invite_token_hash == ""


def test_seed_admin_emails_by_default(tenant):
    run("seed_tenant_admin", tenant="gehu", email="admin@gehu.test", name="Admin")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["admin@gehu.test"]
    assert "https://gehu.testserver/invite/" in mail.outbox[0].body


def test_seed_admin_refuses_duplicate_email(tenant):
    run("seed_tenant_admin", tenant="gehu", email="admin@gehu.test", name="Admin", print_link=True)
    with pytest.raises(CommandError):
        run(
            "seed_tenant_admin",
            tenant="gehu",
            email="admin@gehu.test",
            name="Admin",
            print_link=True,
        )


def test_create_tenant_rejects_duplicates_and_bad_slugs(tenant):
    with pytest.raises(CommandError):
        run("create_tenant", name="Again", slug="gehu")
    with pytest.raises(CommandError):
        run("create_tenant", name="Dotted", slug="a.b")
    with pytest.raises(CommandError):
        run("create_tenant", name="Spaced", slug="a b")


def test_create_roles_adds_presets_without_removing_permissions(tenant):
    with tenant_scope(tenant.id):
        Role.objects.create(name="Faculty", permissions=["timetable.view", "data.export"])
        Role.objects.create(name="Admin", permissions=["timetable.view"])
    run("create_roles", tenant="gehu")
    with tenant_scope(tenant.id):
        assert set(Role.objects.values_list("name", flat=True)) == set(ROLE_PRESETS)
        faculty = set(Role.objects.get(name="Faculty").permissions)
        assert faculty == {"timetable.view", "data.export"}
        admin = set(Role.objects.get(name="Admin").permissions)
        assert admin == set(ROLE_PRESETS["Admin"])
        assert AuditEvent.objects.filter(action="role.updated").count() == 1
        assert AuditEvent.objects.filter(action="role.created").count() == 1
    run("create_roles", tenant="gehu")
    with tenant_scope(tenant.id):
        assert AuditEvent.objects.filter(action__startswith="role.").count() == 2


def test_suspend_and_unsuspend_tenant(tenant):
    client = Client(headers={"Host": HOST})
    assert client.get(reverse("login")).status_code == 200
    run("suspend_tenant", tenant="gehu")
    tenant.refresh_from_db()
    assert tenant.archived
    assert client.get(reverse("login")).status_code == 404
    run("suspend_tenant", tenant="gehu", unsuspend=True)
    tenant.refresh_from_db()
    assert not tenant.archived
    assert client.get(reverse("login")).status_code == 200
    with tenant_scope(tenant.id):
        actions = list(AuditEvent.objects.order_by("created_at").values_list("action", flat=True))
    assert actions == ["tenant.suspended", "tenant.unsuspended"]


def test_commands_reject_unknown_tenant(db):
    for command in ("create_roles", "suspend_tenant"):
        with pytest.raises(CommandError):
            run(command, tenant="missing")
    with pytest.raises(CommandError):
        run("seed_tenant_admin", tenant="missing", email="a@b.test", name="A")
