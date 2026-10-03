import uuid
from contextlib import contextmanager

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, models, transaction
from django.http import HttpResponseForbidden, HttpResponseNotFound

from core.ctx import request_id
from core.ctx import tenant_id as _tenant_id


class TenantUnset(RuntimeError):
    pass


def current_tenant_id():
    return _tenant_id.get()


def require_tenant_id():
    tenant_id = _tenant_id.get()
    if tenant_id is None:
        raise TenantUnset("no tenant in the current context")
    return tenant_id


def set_db_tenant(tenant_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id or "")])


def db_tenant():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.tenant_id', true)")
        return cursor.fetchone()[0] or ""


@contextmanager
def tenant_scope(tenant_id):
    token = _tenant_id.set(tenant_id)
    previous = db_tenant() if connection.in_atomic_block else ""
    try:
        with transaction.atomic():
            set_db_tenant(tenant_id)
            yield tenant_id
    finally:
        _tenant_id.reset(token)
        if connection.in_atomic_block and not connection.needs_rollback:
            set_db_tenant(previous)


class TenantManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=require_tenant_id())

    def create(self, **kwargs):
        if "tenant" not in kwargs:
            kwargs.setdefault("tenant_id", require_tenant_id())
        return super().create(**kwargs)


class TenantModel(models.Model):
    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, editable=False)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        current = current_tenant_id()
        if self.tenant_id is None:
            self.tenant_id = require_tenant_id()
        elif current is not None and self.tenant_id != current:
            raise PermissionDenied("cross-tenant write")
        super().save(*args, **kwargs)


def host_slug(request):
    host = request.get_host().split(":")[0].lower()
    suffix = "." + settings.BASE_DOMAIN
    if not host.endswith(suffix):
        return None
    slug = host[: -len(suffix)]
    return slug if slug and "." not in slug else None


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request_id.set(request.headers.get("X-Request-ID", "")[:36] or str(uuid.uuid4()))
        try:
            request.request_id = request_id.get()
            if request.path == settings.HEALTH_PATH:
                return self.get_response(request)
            return self.scoped(request)
        finally:
            request_id.reset(token)

    def scoped(self, request):
        from core.models import Tenant

        slug = host_slug(request)
        tenant = Tenant.objects.filter(slug=slug, archived=False).first() if slug else None
        if tenant is None:
            return HttpResponseNotFound("unknown tenant")
        request.tenant = tenant
        with tenant_scope(tenant.id):
            if request.user.is_authenticated and request.user.tenant_id != tenant.id:
                from django.contrib.auth import logout

                logout(request)
                return HttpResponseForbidden()
            return self.get_response(request)
