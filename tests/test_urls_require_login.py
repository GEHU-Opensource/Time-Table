import uuid

import pytest
from django.test import Client
from django.urls import URLResolver, reverse
from django.urls.converters import IntConverter, UUIDConverter

pytestmark = pytest.mark.django_db

PUBLIC = {"login", "health", "invite-accept", "invite-set-password"}


def dummy_value(name, converter):
    if isinstance(converter, UUIDConverter):
        return uuid.uuid4()
    if isinstance(converter, IntConverter):
        return 1
    return "tok" if name == "token" else "x"


def walk(patterns):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from walk(pattern.url_patterns)
        elif pattern.name:
            converters = pattern.pattern.converters
            yield pattern.name, {name: dummy_value(name, conv) for name, conv in converters.items()}


def root_urls():
    from config.urls import urlpatterns

    return [(name, reverse(name, kwargs=kwargs)) for name, kwargs in walk(urlpatterns)]


def is_public(name):
    return name in PUBLIC or name.startswith("password-reset")


def test_every_private_url_hides_from_anonymous(client, tenant):
    login_url = reverse("login")
    checked, failures = [], []
    for name, url in root_urls():
        if is_public(name):
            continue
        response = client.get(url)
        checked.append(name)
        if response.status_code == 302:
            if not response.url.startswith(login_url):
                failures.append(f"{name} -> {response.url}")
        elif response.status_code not in (404, 405):
            failures.append(f"{name} -> {response.status_code}")
    assert failures == []
    assert {"mfa-setup", "mfa-verify", "logout"} <= set(checked)


def test_public_urls_never_leak_a_server_error(client, tenant):
    for name, url in root_urls():
        if is_public(name):
            assert client.get(url).status_code < 500, name


def test_health_needs_no_tenant(db):
    for host in ("testserver", "nowhere.testserver", "gehu.testserver"):
        response = Client(headers={"Host": host}).get("/healthz/")
        assert response.status_code == 200
        assert response.content == b"ok"
    assert reverse("health") == "/healthz/"
