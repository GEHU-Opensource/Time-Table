import re

import pytest
from django.core import mail
from django.db import connection
from django.test import Client
from django.urls import reverse

from core.models import AuditEvent
from tests.conftest import HOST, PASSWORD

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_perms")]

NEW_PASSWORD = "orbit-lantern-quartz-91"
RESET_LINK = re.compile(r"https?://gehu\.testserver(/reset/[^/\s]+/[^/\s]+/)")


def post_login(client, email, password=PASSWORD):
    return client.post(reverse("login"), {"username": email, "password": password})


def logged_in_as(client, user):
    return client.session.get("_auth_user_id") == str(user.pk)


def test_login_page_renders(client, tenant):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Email" in response.content
    assert b'name="username"' in response.content
    assert b'name="password"' in response.content
    assert response.content.count(b"<script") == 1
    assert b"htmx.min.js" in response.content


def test_correct_password_logs_in(client, faculty_user):
    response = post_login(client, "Faculty@GEHU.test")
    assert response.status_code == 302
    assert response.url == reverse("admin")
    assert logged_in_as(client, faculty_user)
    assert AuditEvent.objects.filter(action="user.login", actor=faculty_user).exists()


def test_login_rotates_session_key(client, faculty_user):
    client.get(reverse("login"))
    before = client.session.session_key
    post_login(client, faculty_user.email)
    assert client.session.session_key != before


def test_wrong_password_does_not_log_in(client, faculty_user):
    response = post_login(client, faculty_user.email, "not the password")
    assert response.status_code == 200
    assert b"errorlist" in response.content
    assert not logged_in_as(client, faculty_user)
    assert not AuditEvent.objects.filter(action="user.login").exists()


def test_unknown_email_does_not_log_in(client, faculty_user):
    response = post_login(client, "ghost@gehu.test")
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_inactive_user_cannot_log_in(client, faculty_user):
    faculty_user.is_active = False
    faculty_user.save(update_fields=["is_active"])
    response = post_login(client, faculty_user.email)
    assert response.status_code == 200
    assert not logged_in_as(client, faculty_user)


def test_user_of_another_tenant_cannot_log_in_here(client, tenant, other_tenant):
    from core.models import User
    from core.tenancy import tenant_scope

    with tenant_scope(other_tenant.id):
        User.objects.create_user("visitor@other.test", "Visitor", password=PASSWORD)
    response = post_login(client, "visitor@other.test")
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_login_works_as_app_role_with_guc(client, tenant, faculty_user, app_role):
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.id)])
    response = post_login(client, faculty_user.email)
    assert response.status_code == 302
    assert logged_in_as(client, faculty_user)


def test_authenticated_user_is_redirected_from_login(as_faculty):
    response = as_faculty.get(reverse("login"))
    assert response.status_code == 302
    assert response.url == reverse("admin")


def test_logout_is_post_only(as_faculty, faculty_user):
    assert as_faculty.get(reverse("logout")).status_code == 405
    assert logged_in_as(as_faculty, faculty_user)
    response = as_faculty.post(reverse("logout"))
    assert response.status_code == 302
    assert response.url == reverse("login")
    assert "_auth_user_id" not in as_faculty.session
    assert AuditEvent.objects.filter(action="user.logout", actor=faculty_user).exists()


def test_session_ends_after_auth_version_bump(as_faculty, faculty_user):
    assert as_faculty.get(reverse("probe-view")).status_code == 200
    faculty_user.auth_version += 1
    faculty_user.save(update_fields=["auth_version"])
    response = as_faculty.get(reverse("probe-view"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_password_reset_flow_changes_password_and_ends_other_sessions(as_faculty, faculty_user):
    assert as_faculty.get(reverse("probe-view")).status_code == 200
    client = Client(headers={"Host": HOST})
    response = client.post(reverse("password-reset"), {"email": faculty_user.email})
    assert response.status_code == 302
    assert response.url == reverse("password-reset-done")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [faculty_user.email]
    path = RESET_LINK.search(mail.outbox[0].body).group(1)

    response = client.get(path)
    assert response.status_code == 302
    response = client.post(
        response.url, {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD}
    )
    assert response.status_code == 302
    assert response.url == reverse("password-reset-complete")
    assert client.get(response.url).status_code == 200

    version = faculty_user.auth_version
    faculty_user.refresh_from_db()
    assert faculty_user.check_password(NEW_PASSWORD)
    assert faculty_user.auth_version == version + 1
    assert AuditEvent.objects.filter(action="user.password_reset", actor=faculty_user).exists()
    assert b"not valid" in client.get(path).content
    assert as_faculty.get(reverse("probe-view")).status_code == 302


def test_password_reset_for_unknown_email_sends_nothing(client, faculty_user):
    response = client.post(reverse("password-reset"), {"email": "ghost@gehu.test"})
    assert response.status_code == 302
    assert mail.outbox == []


def test_password_reset_ignores_other_tenants_users(client, tenant, other_tenant):
    from core.models import User
    from core.tenancy import tenant_scope

    with tenant_scope(other_tenant.id):
        User.objects.create_user("visitor@other.test", "Visitor", password=PASSWORD)
    client.post(reverse("password-reset"), {"email": "visitor@other.test"})
    assert mail.outbox == []
