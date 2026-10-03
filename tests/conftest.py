import pytest
from django.db import connection
from django.test import Client
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import Department, Role, Tenant, User
from core.perms import ROLE_PRESETS
from core.tenancy import tenant_scope

PASSWORD = "correct horse battery staple"
HOST = "gehu.testserver"


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="GEHU", slug="gehu")


@pytest.fixture
def other_tenant(db):
    return Tenant.objects.create(name="Other University", slug="other")


@pytest.fixture
def scope(tenant):
    with tenant_scope(tenant.id):
        yield tenant


@pytest.fixture
def department(scope):
    return Department.objects.create(name="CSE")


@pytest.fixture
def roles(scope):
    return {
        name: Role.objects.create(name=name, permissions=list(permissions))
        for name, permissions in ROLE_PRESETS.items()
    }


@pytest.fixture
def admin_user(roles):
    return User.objects.create_user(
        "admin@gehu.test", "Admin", password=PASSWORD, role=roles["Admin"]
    )


@pytest.fixture
def hod_user(roles, department):
    return User.objects.create_user(
        "hod@gehu.test", "HOD", password=PASSWORD, role=roles["HOD"], department=department
    )


@pytest.fixture
def faculty_user(roles):
    return User.objects.create_user(
        "faculty@gehu.test", "Faculty", password=PASSWORD, role=roles["Faculty"]
    )


@pytest.fixture
def client():
    return Client(headers={"Host": HOST})


def login(client, user):
    client.force_login(user, backend="core.auth.TenantBackend")
    if user.needs_mfa:
        device, _ = TOTPDevice.objects.get_or_create(
            user=user, confirmed=True, defaults={"name": "test"}
        )
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
    return client


@pytest.fixture
def as_admin(client, admin_user):
    return login(client, admin_user)


@pytest.fixture
def as_hod(client, hod_user):
    return login(client, hod_user)


@pytest.fixture
def as_faculty(client, faculty_user):
    return login(client, faculty_user)


@pytest.fixture
def app_role(db):
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE tt_app")
    yield
    with connection.cursor() as cursor:
        cursor.execute("RESET ROLE")
