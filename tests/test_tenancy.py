import pytest
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from core.models import Department, User
from core.tenancy import TenantUnset, current_tenant_id, tenant_scope
from tests.conftest import HOST

pytestmark = pytest.mark.django_db


def test_objects_outside_scope_raise(db):
    assert current_tenant_id() is None
    with pytest.raises(TenantUnset):
        list(Department.objects.all())
    with pytest.raises(TenantUnset):
        User.objects.filter(email="x@gehu.test").exists()


def test_create_outside_scope_raises(db):
    with pytest.raises(TenantUnset):
        Department.objects.create(name="CSE")


def test_rows_of_one_tenant_are_invisible_to_another(scope, other_tenant):
    created = Department.objects.create(name="CSE")
    with tenant_scope(other_tenant.id):
        assert Department.objects.count() == 0
        assert not Department.objects.filter(pk=created.pk).exists()
        Department.objects.create(name="CSE")
        assert Department.objects.count() == 1
    assert current_tenant_id() == scope.id
    assert list(Department.objects.values_list("pk", flat=True)) == [created.pk]
    assert Department.all_objects.count() == 2


def test_saving_with_another_tenants_id_raises(scope, other_tenant):
    with pytest.raises(PermissionDenied):
        Department(name="Foreign", tenant_id=other_tenant.id).save()
    department = Department.objects.create(name="Home")
    department.tenant_id = other_tenant.id
    with pytest.raises(PermissionDenied):
        department.save()


def test_save_fills_tenant_from_scope(scope):
    department = Department(name="CSE")
    department.save()
    assert department.tenant_id == scope.id


def test_unknown_host_returns_404(tenant):
    response = Client(headers={"Host": "nowhere.testserver"}).get(reverse("login"))
    assert response.status_code == 404


def test_bare_base_domain_returns_404(tenant):
    response = Client(headers={"Host": "testserver"}).get(reverse("login"))
    assert response.status_code == 404


def test_archived_tenant_returns_404(tenant):
    tenant.archived = True
    tenant.save(update_fields=["archived"])
    response = Client(headers={"Host": HOST}).get(reverse("login"))
    assert response.status_code == 404


def test_user_of_other_tenant_is_anonymous_on_foreign_host(as_faculty, other_tenant):
    response = as_faculty.get(reverse("mfa-setup"), headers={"Host": "other.testserver"})
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))
    assert as_faculty.get(reverse("mfa-setup")).status_code == 200
