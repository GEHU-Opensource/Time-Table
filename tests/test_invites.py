import json
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core import invites
from core.models import AuditEvent, User
from tests.conftest import HOST

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_perms")]

NEW_PASSWORD = "orbit-lantern-quartz-91"
LINK = re.compile(r"https://gehu\.testserver/invite/([A-Za-z0-9_-]+)/")


def invite(actor, roles, email="new@gehu.test"):
    user = invites.invite_user(actor, email=email, name="New Person", role=roles["Faculty"])
    token = LINK.search(mail.outbox[-1].body).group(1)
    return user, token


def accept(client, token):
    response = client.get(reverse("invite-accept", kwargs={"token": token}))
    if response.status_code != 302:
        return response
    return client.post(
        reverse("invite-set-password"),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )


def test_invite_creates_user_without_password_and_sends_one_email(admin_user, roles):
    user = invites.invite_user(
        admin_user, email="New@GEHU.test", name="New Person", role=roles["Faculty"]
    )
    assert user.email == "new@gehu.test"
    assert not user.has_usable_password()
    assert user.invite_token_hash
    assert user.invite_expires_at > timezone.now() + timedelta(hours=71)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["new@gehu.test"]
    token = LINK.search(message.body).group(1)
    assert invites.hash_token(token) == user.invite_token_hash
    html, media_type = message.alternatives[0]
    assert media_type == "text/html"
    assert LINK.search(html).group(1) == token

    event = AuditEvent.objects.get(action="user.invited", object_id=user.id)
    assert event.actor == admin_user
    assert "new@gehu.test" not in json.dumps(event.after)
    assert event.after["role"] == "Faculty"


def test_accepting_sets_password_and_logs_in(client, admin_user, roles):
    user, token = invite(admin_user, roles)
    response = client.get(reverse("invite-accept", kwargs={"token": token}))
    assert response.status_code == 302
    assert response.url == reverse("invite-set-password")
    assert token not in response.url
    assert client.get(response.url).status_code == 200

    response = client.post(
        reverse("invite-set-password"),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    assert response.url == reverse("admin")
    assert client.session["_auth_user_id"] == str(user.pk)

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert user.invite_token_hash == ""
    assert user.invite_expires_at is None
    assert user.auth_version == 2
    assert AuditEvent.objects.filter(action="user.activated", object_id=user.id).exists()
    assert client.get(reverse("probe-view")).status_code == 200


def test_second_acceptance_of_same_token_fails(client, admin_user, roles):
    user, token = invite(admin_user, roles)
    assert accept(client, token).status_code == 302
    again = Client(headers={"Host": HOST})
    response = again.get(reverse("invite-accept", kwargs={"token": token}))
    assert response.status_code == 404
    assert "_auth_user_id" not in again.session
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


def test_expired_token_fails(client, admin_user, roles):
    user, token = invite(admin_user, roles)
    user.invite_expires_at = timezone.now() - timedelta(seconds=1)
    user.save(update_fields=["invite_expires_at"])
    response = client.get(reverse("invite-accept", kwargs={"token": token}))
    assert response.status_code == 404
    assert client.get(reverse("invite-set-password")).status_code == 404
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_wrong_token_fails(client, admin_user, roles):
    invite(admin_user, roles)
    response = client.get(reverse("invite-accept", kwargs={"token": "not-a-real-token"}))
    assert response.status_code == 404


def test_set_password_without_session_token_fails(client, admin_user, roles):
    invite(admin_user, roles)
    assert client.get(reverse("invite-set-password")).status_code == 404
    response = client.post(
        reverse("invite-set-password"),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 404


def test_weak_password_is_rejected(client, admin_user, roles):
    user, token = invite(admin_user, roles)
    client.get(reverse("invite-accept", kwargs={"token": token}))
    response = client.post(
        reverse("invite-set-password"), {"new_password1": "short", "new_password2": "short"}
    )
    assert response.status_code == 200
    assert b"errorlist" in response.content
    user.refresh_from_db()
    assert not user.has_usable_password()
    assert user.invite_token_hash == invites.hash_token(token)


def test_concurrent_claims_cannot_both_succeed(admin_user, roles):
    user, token = invite(admin_user, roles)
    token_hash = invites.hash_token(token)
    assert invites.claim_invite(user, token_hash)
    assert not invites.claim_invite(user, token_hash)
    assert not invites.claim_invite(user, "")
    assert not invites.activate(user, token_hash, NEW_PASSWORD)
    user.refresh_from_db()
    assert not user.has_usable_password()


def test_resend_replaces_the_token(client, admin_user, roles):
    user, old_token = invite(admin_user, roles)
    invites.resend_invite(admin_user, user)
    assert len(mail.outbox) == 2
    new_token = LINK.search(mail.outbox[1].body).group(1)
    assert new_token != old_token
    assert client.get(reverse("invite-accept", kwargs={"token": old_token})).status_code == 404
    assert accept(client, new_token).status_code == 302
    assert AuditEvent.objects.filter(action="user.invite_resent", object_id=user.id).exists()


def test_invite_is_scoped_to_the_tenant_host(admin_user, roles, other_tenant):
    user, token = invite(admin_user, roles)
    response = Client(headers={"Host": "other.testserver"}).get(
        reverse("invite-accept", kwargs={"token": token})
    )
    assert response.status_code == 404
    assert User.objects.get(pk=user.pk).invite_token_hash == invites.hash_token(token)
