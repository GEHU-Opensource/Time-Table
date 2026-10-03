import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from core.audit import audit
from core.models import AuditEvent, Role, User
from core.perms import Perm
from core.tenancy import tenant_scope

pytestmark = pytest.mark.django_db

INSERT_USER = """
INSERT INTO core_user
  (id, password, email, name, is_active, auth_version, invite_token_hash, created_at,
   role_id, tenant_id)
VALUES (gen_random_uuid(), '', %s, 'Probe', true, 1, '', now(), %s, %s)
"""


def set_guc(cursor, tenant_id):
    cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id or "")])


def count_users(cursor):
    cursor.execute("SELECT count(*) FROM core_user")
    return cursor.fetchone()[0]


@pytest.fixture
def other_user(other_tenant):
    with tenant_scope(other_tenant.id):
        role = Role.objects.create(name="Faculty", permissions=[Perm.TIMETABLE_VIEW.value])
        return User.objects.create_user("faculty@other.test", "Other", role=role)


def test_app_role_sees_only_the_current_tenant(tenant, faculty_user, other_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        assert count_users(cursor) == 1
        cursor.execute("SELECT email FROM core_user")
        assert cursor.fetchone()[0] == faculty_user.email
        set_guc(cursor, other_user.tenant_id)
        assert count_users(cursor) == 1
        cursor.execute("SELECT email FROM core_user")
        assert cursor.fetchone()[0] == other_user.email


def test_app_role_sees_nothing_without_tenant(tenant, faculty_user, other_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, None)
        assert count_users(cursor) == 0
        cursor.execute("SELECT count(*) FROM core_role")
        assert cursor.fetchone()[0] == 0


def test_insert_for_another_tenant_is_rejected(tenant, other_tenant, faculty_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        with pytest.raises(DatabaseError), transaction.atomic():
            cursor.execute(INSERT_USER, ["probe@other.test", None, other_tenant.id])
        assert count_users(cursor) == 1


def test_insert_referencing_another_tenants_role_fails(tenant, faculty_user, other_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        with pytest.raises(IntegrityError), transaction.atomic():
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute(INSERT_USER, ["probe@gehu.test", other_user.role_id, tenant.id])
        assert count_users(cursor) == 1


def test_insert_referencing_own_tenants_role_succeeds(tenant, faculty_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        with transaction.atomic():
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute(INSERT_USER, ["probe@gehu.test", faculty_user.role_id, tenant.id])
        assert count_users(cursor) == 2


def test_audit_rows_cannot_be_changed_by_app_role(tenant, faculty_user, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        event = audit(faculty_user, "probe", faculty_user)
        for sql in (
            "UPDATE core_auditevent SET action = 'tampered' WHERE id = %s",
            "DELETE FROM core_auditevent WHERE id = %s",
        ):
            with pytest.raises(DatabaseError), transaction.atomic():
                cursor.execute(sql, [event.id])
        assert AuditEvent.objects.get(pk=event.pk).action == "probe"


def test_audit_rows_cannot_be_changed_by_owner(tenant, faculty_user):
    event = audit(faculty_user, "probe", faculty_user)
    with connection.cursor() as cursor:
        for sql in (
            "UPDATE core_auditevent SET action = 'tampered' WHERE id = %s",
            "DELETE FROM core_auditevent WHERE id = %s",
        ):
            with pytest.raises(IntegrityError), transaction.atomic():
                cursor.execute(sql, [event.id])
    assert AuditEvent.objects.get(pk=event.pk).action == "probe"


def test_app_role_cannot_create_tenants(tenant, app_role):
    with connection.cursor() as cursor:
        set_guc(cursor, tenant.id)
        with pytest.raises(DatabaseError), transaction.atomic():
            cursor.execute(
                "INSERT INTO core_tenant (id, name, slug, settings, archived, created_at) "
                "VALUES (gen_random_uuid(), 'Rogue', 'rogue', '{}', false, now())"
            )
