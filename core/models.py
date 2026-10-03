import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils.crypto import salted_hmac

from core.perms import PRIVILEGED, Perm
from core.tenancy import TenantManager, TenantModel


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=40, unique=True)
    settings = models.JSONField(default=dict, blank=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Department(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="department_name_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="department_tenant_id_unique"),
        ]

    def __str__(self):
        return self.name


class Role(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60)
    permissions = ArrayField(models.CharField(max_length=40), default=list, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="role_name_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="role_tenant_id_unique"),
            models.CheckConstraint(
                condition=Q(permissions__contained_by=[p.value for p in Perm]),
                name="role_permissions_known",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        unknown = set(self.permissions) - {p.value for p in Perm}
        if unknown:
            raise ValueError(f"unknown permissions: {sorted(unknown)}")
        super().save(*args, **kwargs)

    @property
    def privileged(self):
        return bool(PRIVILEGED & set(self.permissions))


class UserManager(TenantManager, BaseUserManager):
    def create_user(self, email, name, password=None, **extra):
        user = self.model(email=self.normalize_email(email).lower(), name=name, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def get_by_natural_key(self, email):
        return self.get(email=email.lower())


class User(AbstractBaseUser, TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    name = models.CharField(max_length=150)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auth_version = models.PositiveIntegerField(default=1)
    invite_token_hash = models.CharField(max_length=64, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()
    all_objects = BaseUserManager()

    class Meta:
        ordering = ["email"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="user_email_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="user_tenant_id_unique"),
        ]

    def __str__(self):
        return self.email

    @property
    def perms(self):
        return frozenset(self.role.permissions) if self.role_id else frozenset()

    @property
    def needs_mfa(self):
        return bool(PRIVILEGED & self.perms)

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def _get_session_auth_hash(self, secret=None):
        return salted_hmac(
            "core.User.session_auth_hash",
            f"{self.password}:{self.auth_version}",
            secret=secret,
            algorithm="sha256",
        ).hexdigest()


class AuditEvent(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    request_id = models.CharField(max_length=36, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["tenant", "created_at"])]
