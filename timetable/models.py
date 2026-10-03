import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from core.models import Department, User
from core.tenancy import TenantManager, TenantModel


class ScopedQuerySet(models.QuerySet):
    department_path = "department_id"

    def visible_to(self, user):
        if user.department_id is None:
            return self
        return self.filter(
            Q(**{self.department_path: user.department_id})
            | Q(**{f"{self.department_path}__isnull": True})
        )

    def owned_by(self, user):
        if user.department_id is None:
            return self
        return self.filter(**{self.department_path: user.department_id})


class TimetableScopedQuerySet(ScopedQuerySet):
    department_path = "timetable__department_id"


class VersionScopedQuerySet(ScopedQuerySet):
    department_path = "version__timetable__department_id"


class Resource(TenantModel):
    class Kind(models.TextChoices):
        TEACHER = "teacher"
        ROOM = "room"
        SECTION = "section"
        BATCH = "batch"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120, blank=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    max_load = models.PositiveIntegerField(null=True, blank=True)
    unavailable = models.JSONField(default=list, blank=True)
    preferred = models.JSONField(default=list, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="batches"
    )
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="teacher"
    )
    active = models.BooleanField(default=True)

    objects = TenantManager.from_queryset(ScopedQuerySet)()

    class Meta:
        ordering = ["kind", "code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "kind", "code"], name="resource_code_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="resource_tenant_id_unique"),
            models.CheckConstraint(
                condition=Q(kind="batch", parent__isnull=False)
                | (~Q(kind="batch") & Q(parent__isnull=True)),
                name="resource_batch_has_parent",
            ),
            models.CheckConstraint(
                condition=~Q(kind="room") | Q(capacity__gt=0), name="resource_room_has_capacity"
            ),
            models.CheckConstraint(
                condition=~Q(kind="teacher") | Q(max_load__isnull=False),
                name="resource_teacher_has_max_load",
            ),
        ]

    def __str__(self):
        return self.code


class Subject(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    length = models.PositiveSmallIntegerField(default=1)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    active = models.BooleanField(default=True)

    objects = TenantManager.from_queryset(ScopedQuerySet)()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="subject_code_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="subject_tenant_id_unique"),
            models.CheckConstraint(
                condition=Q(length__gte=1, length__lte=4), name="subject_length"
            ),
        ]

    def __str__(self):
        return self.code


class Timetable(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True)
    grid = models.JSONField()
    start_date = models.DateField()
    end_date = models.DateField()
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(ScopedQuerySet)()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="timetable_name_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="timetable_tenant_id_unique"),
            models.CheckConstraint(
                condition=Q(start_date__lte=models.F("end_date")), name="timetable_dates_ordered"
            ),
        ]

    def __str__(self):
        return self.name


class Version(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft"
        SOLVING = "solving"
        FAILED = "failed"
        PUBLISHED = "published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timetable = models.ForeignKey(Timetable, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="children"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    grid = models.JSONField()
    effective_from = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    solver_stats = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(TimetableScopedQuerySet)()

    class Meta:
        ordering = ["timetable", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["timetable", "number"], name="version_number_unique"),
            models.UniqueConstraint(fields=["tenant", "id"], name="version_tenant_id_unique"),
            models.UniqueConstraint(
                fields=["timetable", "effective_from"],
                condition=Q(status="published"),
                name="version_one_published_per_date",
            ),
            models.UniqueConstraint(
                fields=["timetable"], condition=Q(status="solving"), name="version_one_solving"
            ),
            models.CheckConstraint(
                condition=~Q(status="published") | Q(effective_from__isnull=False),
                name="version_published_has_date",
            ),
        ]

    def __str__(self):
        return f"{self.timetable} v{self.number}"


class Requirement(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name="requirements")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    sessions = models.PositiveSmallIntegerField()
    length = models.PositiveSmallIntegerField(default=1)
    room_tag = models.CharField(max_length=30, blank=True)
    rooms_needed = models.PositiveSmallIntegerField(default=1)
    fixed_slots = models.JSONField(default=list, blank=True)

    objects = TenantManager.from_queryset(VersionScopedQuerySet)()

    class Meta:
        ordering = ["subject__code"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "id"], name="requirement_tenant_id_unique"),
            models.CheckConstraint(condition=Q(sessions__gte=1), name="requirement_sessions"),
            models.CheckConstraint(
                condition=Q(length__gte=1, length__lte=4), name="requirement_length"
            ),
            models.CheckConstraint(condition=Q(rooms_needed__lte=8), name="requirement_rooms"),
        ]


class RequirementResource(TenantModel):
    class Role(models.TextChoices):
        TEACHER = "teacher"
        ATTENDEE = "attendee"
        FIXED_ROOM = "fixed_room"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name="participants"
    )
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requirement", "resource"], name="requirement_resource_unique"
            ),
        ]


class Assignment(TenantModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(Version, on_delete=models.CASCADE, related_name="assignments")
    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name="assignments"
    )
    session = models.PositiveSmallIntegerField()
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="+")
    day = models.PositiveSmallIntegerField()
    period = models.PositiveSmallIntegerField()
    serves = models.ForeignKey(
        Resource, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    is_live = models.BooleanField(default=False)

    objects = TenantManager.from_queryset(VersionScopedQuerySet)()

    class Meta:
        ordering = ["day", "period"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "resource", "day", "period"], name="assignment_slot_unique"
            ),
            models.UniqueConstraint(
                fields=["tenant", "resource", "day", "period"],
                condition=Q(is_live=True),
                name="assignment_live_slot_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["version", "requirement"]),
            models.Index(fields=["tenant", "is_live"]),
        ]
