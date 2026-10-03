import pytest
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.auth import BACKEND_PATH
from core.models import AuditEvent

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.test_perms")]


def current_token(device, drift=0):
    return f"{totp(device.bin_key, device.step, device.t0, device.digits, drift):06d}"


def wrong_token(device):
    nearby = {current_token(device, drift) for drift in (-2, -1, 0, 1, 2)}
    candidate = 0
    while f"{candidate:06d}" in nearby:
        candidate += 1
    return f"{candidate:06d}"


def test_admin_without_device_is_sent_to_setup(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    response = client.get(reverse("probe-manage"))
    assert response.status_code == 302
    assert response.url == reverse("mfa-setup")


def test_setup_page_shows_qr_and_pending_device(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    response = client.get(reverse("mfa-setup"))
    assert response.status_code == 200
    assert b'src="data:image/' in response.content
    assert TOTPDevice.objects.filter(user=admin_user, confirmed=False).count() == 1
    client.get(reverse("mfa-setup"))
    assert TOTPDevice.objects.filter(user=admin_user, confirmed=False).count() == 1


def test_confirming_token_enables_mfa_and_unlocks_pages(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    client.get(reverse("mfa-setup"))
    device = TOTPDevice.objects.get(user=admin_user, confirmed=False)
    response = client.post(reverse("mfa-setup"), {"token": current_token(device)})
    assert response.status_code == 302
    assert response.url == reverse("admin")
    device.refresh_from_db()
    assert device.confirmed
    assert client.get(reverse("probe-manage")).status_code == 200
    assert AuditEvent.objects.filter(action="mfa.enabled", actor=admin_user).exists()


def test_wrong_token_does_not_confirm(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    client.get(reverse("mfa-setup"))
    device = TOTPDevice.objects.get(user=admin_user, confirmed=False)
    response = client.post(reverse("mfa-setup"), {"token": wrong_token(device)})
    assert response.status_code == 200
    assert b"errorlist" in response.content
    device.refresh_from_db()
    assert not device.confirmed
    assert client.get(reverse("probe-manage")).url == reverse("mfa-setup")
    assert AuditEvent.objects.filter(action="mfa.setup_failed", actor=admin_user).exists()


def test_malformed_token_is_rejected_by_the_form(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    response = client.post(reverse("mfa-setup"), {"token": "abc"})
    assert response.status_code == 200
    assert b"6-digit" in response.content


def test_user_with_confirmed_device_verifies(client, admin_user):
    device = TOTPDevice.objects.create(user=admin_user, confirmed=True, name="phone")
    client.force_login(admin_user, backend=BACKEND_PATH)
    response = client.get(reverse("probe-manage"))
    assert response.status_code == 302
    assert response.url == reverse("mfa-verify")
    assert client.get(reverse("mfa-verify")).status_code == 200

    response = client.post(reverse("mfa-verify"), {"token": wrong_token(device)})
    assert response.status_code == 200
    assert client.get(reverse("probe-manage")).status_code == 302
    assert AuditEvent.objects.filter(action="mfa.verify_failed", actor=admin_user).exists()

    device.refresh_from_db()
    device.throttle_reset()
    response = client.post(reverse("mfa-verify"), {"token": current_token(device)})
    assert response.status_code == 302
    assert response.url == reverse("admin")
    assert client.get(reverse("probe-manage")).status_code == 200
    assert AuditEvent.objects.filter(action="mfa.verified", actor=admin_user).exists()


def test_verify_without_confirmed_device_goes_to_setup(client, admin_user):
    client.force_login(admin_user, backend=BACKEND_PATH)
    response = client.get(reverse("mfa-verify"))
    assert response.status_code == 302
    assert response.url == reverse("mfa-setup")


def test_faculty_is_never_asked_for_mfa(client, faculty_user):
    client.force_login(faculty_user, backend=BACKEND_PATH)
    assert client.get(reverse("probe-view")).status_code == 200
    assert not TOTPDevice.objects.filter(user=faculty_user).exists()


def test_hod_is_never_asked_for_mfa(client, hod_user):
    client.force_login(hod_user, backend=BACKEND_PATH)
    assert client.get(reverse("probe-manage")).status_code == 200


def test_mfa_pages_require_login(client, tenant):
    for name in ("mfa-setup", "mfa-verify"):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
