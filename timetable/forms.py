import re

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Department, Role
from core.perms import PERM_LABELS, Perm
from timetable import grids
from timetable.models import Requirement, RequirementResource, Resource, Subject, Version

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
PERIOD_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DATE_INPUT = forms.DateInput(attrs={"type": "date"})


def visible(queryset, user):
    queryset = queryset.visible_to(user)
    if user.department_id is None:
        return queryset
    path = queryset.department_path
    return queryset.filter(Q(**{path: user.department_id}) | Q(**{f"{path}__isnull": True}))


def department_field(user):
    if user.department_id is None:
        return forms.ModelChoiceField(
            Department.objects.all(), required=False, empty_label="Shared (all departments)"
        )
    return forms.ModelChoiceField(
        Department.objects.filter(pk=user.department_id),
        required=True,
        initial=user.department_id,
        empty_label=None,
    )


def comma_list(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def to_minutes(hours, minutes):
    return int(hours) * 60 + int(minutes)


class TimetableForm(forms.Form):
    name = forms.CharField(max_length=120, help_text="For example: CSE Semester 3")
    days = forms.MultipleChoiceField(
        label="Working days",
        choices=[(day, day) for day in DAYS],
        widget=forms.CheckboxSelectMultiple,
        initial=DAYS[:6],
    )
    periods = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
        initial="\n".join(f"{start}-{end}" for start, end in grids.DEFAULT_GRID["periods"]),
        help_text="One period per line as start-end, for example 09:00-10:00",
    )
    breaks_after = forms.CharField(
        label="Break after period",
        required=False,
        initial="4",
        help_text="Period numbers followed by a break, for example 4 for lunch after period 4",
    )
    start_date = forms.DateField(label="Term starts", widget=DATE_INPUT)
    end_date = forms.DateField(label="Term ends", widget=DATE_INPUT)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"] = department_field(user)
        self.order_fields(
            ["name", "department", "start_date", "end_date", "days", "periods", "breaks_after"]
        )

    def clean_days(self):
        chosen = set(self.cleaned_data["days"])
        return [day for day in DAYS if day in chosen]

    def clean_periods(self):
        periods = []
        previous_end = -1
        for line in self.cleaned_data["periods"].splitlines():
            line = line.strip()
            if not line:
                continue
            match = PERIOD_RE.match(line)
            if match is None:
                raise forms.ValidationError(f"'{line}' is not HH:MM-HH:MM")
            start = to_minutes(match.group(1), match.group(2))
            end = to_minutes(match.group(3), match.group(4))
            if not (0 <= start < end <= 24 * 60) or int(match.group(2)) > 59:
                raise forms.ValidationError(f"'{line}' does not end after it starts")
            if start < previous_end:
                raise forms.ValidationError(f"'{line}' overlaps the previous period")
            previous_end = end
            periods.append([line[:5], line[6:]])
        if not periods:
            raise forms.ValidationError("At least one period is needed")
        return periods

    def clean_breaks_after(self):
        breaks = []
        for token in comma_list(self.cleaned_data["breaks_after"]):
            if not token.isdigit() or int(token) < 1:
                raise forms.ValidationError(f"'{token}' is not a period number")
            breaks.append(int(token) - 1)
        return sorted(set(breaks))

    def clean(self):
        data = super().clean()
        periods = data.get("periods")
        breaks = data.get("breaks_after")
        if periods and breaks and breaks[-1] >= len(periods) - 1:
            self.add_error("breaks_after", "A break must fall between two periods")
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "End date is before the start date")
        return data

    def grid(self):
        return {
            "days": self.cleaned_data["days"],
            "periods": self.cleaned_data["periods"],
            "breaks_after": self.cleaned_data["breaks_after"],
        }


class VersionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, version):
        return f"Copy of v{version.number} ({version.status})"


class DraftForm(forms.Form):
    reason = forms.CharField(required=False, max_length=400, label="Note (optional)")

    def __init__(self, timetable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        versions = Version.objects.filter(timetable=timetable).order_by("-number")
        self.fields["parent"] = VersionChoiceField(
            versions,
            required=False,
            label="Start from",
            empty_label="Empty (no requirements)",
            initial=versions.first(),
        )
        self.order_fields(["parent", "reason"])


def code_and_name(item):
    if item.name and item.name != item.code:
        return f"{item.code} - {item.name}"
    return item.code


class NamedChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, item):
        return code_and_name(item)


class NamedMultipleChoiceField(forms.ModelMultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def label_from_instance(self, item):
        return code_and_name(item)


class RequirementForm(forms.Form):
    ADVANCED = ("length", "room_tag", "rooms_needed", "fixed_room", "fixed_slots")

    sessions = forms.IntegerField(min_value=1, max_value=40, initial=1, label="Classes per week")
    length = forms.IntegerField(
        min_value=1,
        max_value=4,
        required=False,
        label="Periods per class",
        help_text="Leave blank to use the subject's length",
    )
    room_tag = forms.CharField(
        max_length=30,
        required=False,
        label="Room type",
        help_text="Only use rooms with this tag, for example lab. Blank means any room",
    )
    rooms_needed = forms.IntegerField(
        min_value=0, max_value=8, initial=1, help_text="Usually 1. Use 0 when no room is needed"
    )
    fixed_slots = forms.CharField(
        required=False,
        label="Fixed day and period",
        help_text="For example 'Mon 1, Tue 3' (day and period number)",
    )

    def __init__(self, user, version, *args, instance=None, **kwargs):
        self.version = version
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from(instance)
        super().__init__(*args, **kwargs)
        resources = visible(Resource.objects, user).filter(active=True)
        self.fields["subject"] = NamedChoiceField(
            visible(Subject.objects, user).filter(active=True), empty_label="Choose a subject"
        )
        self.fields["teachers"] = NamedMultipleChoiceField(
            resources.filter(kind=Resource.Kind.TEACHER)
        )
        self.fields["attendees"] = NamedMultipleChoiceField(
            resources.filter(kind__in=[Resource.Kind.SECTION, Resource.Kind.BATCH]),
            label="Sections or batches",
        )
        self.fields["fixed_room"] = NamedChoiceField(
            resources.filter(kind=Resource.Kind.ROOM),
            required=False,
            label="Always in this room",
            empty_label="Any room",
        )
        self.order_fields(
            [
                "subject",
                "teachers",
                "attendees",
                "sessions",
                "length",
                "room_tag",
                "rooms_needed",
                "fixed_room",
                "fixed_slots",
            ]
        )

    @property
    def missing(self):
        needed = (("subject", "subjects"), ("teachers", "teachers"), ("attendees", "sections"))
        return [label for name, label in needed if not self.fields[name].queryset.exists()]

    @property
    def advanced_open(self):
        return self.instance is not None or any(self[name].errors for name in self.ADVANCED)

    def initial_from(self, requirement):
        participants = list(requirement.participants.all())

        def with_role(role):
            return [p.resource_id for p in participants if p.role == role]

        fixed_rooms = with_role(RequirementResource.Role.FIXED_ROOM)
        return {
            "subject": requirement.subject_id,
            "teachers": with_role(RequirementResource.Role.TEACHER),
            "attendees": with_role(RequirementResource.Role.ATTENDEE),
            "sessions": requirement.sessions,
            "length": requirement.length,
            "room_tag": requirement.room_tag,
            "rooms_needed": requirement.rooms_needed,
            "fixed_room": fixed_rooms[0] if fixed_rooms else None,
            "fixed_slots": grids.format_fixed_slots(
                requirement.fixed_slots, requirement.version.grid
            ),
        }

    def clean_fixed_slots(self):
        try:
            return grids.parse_fixed_slots(self.cleaned_data["fixed_slots"], self.version.grid)
        except ValueError as error:
            raise forms.ValidationError(str(error)) from error

    def clean(self):
        data = super().clean()
        subject = data.get("subject")
        if subject is not None and not data.get("length"):
            data["length"] = subject.length
        slots = data.get("fixed_slots") or []
        if data.get("sessions") and len(slots) > data["sessions"]:
            self.add_error("fixed_slots", "More fixed slots than sessions")
        length = data.get("length") or 1
        for _, start in slots:
            if start + length > len(self.version.grid["periods"]):
                self.add_error("fixed_slots", "A fixed slot runs past the last period")
                break
        return data

    def participants(self):
        data = self.cleaned_data
        rows = [(r, RequirementResource.Role.TEACHER) for r in data["teachers"]]
        rows += [(r, RequirementResource.Role.ATTENDEE) for r in data["attendees"]]
        if data.get("fixed_room") is not None:
            rows.append((data["fixed_room"], RequirementResource.Role.FIXED_ROOM))
        return rows

    def save(self):
        data = self.cleaned_data
        requirement = self.instance or Requirement(version=self.version)
        requirement.subject = data["subject"]
        requirement.sessions = data["sessions"]
        requirement.length = data["length"]
        requirement.room_tag = data["room_tag"]
        requirement.rooms_needed = data["rooms_needed"]
        requirement.fixed_slots = data["fixed_slots"]
        with transaction.atomic():
            requirement.save()
            requirement.participants.all().delete()
            RequirementResource.objects.bulk_create(
                [
                    RequirementResource(
                        tenant_id=requirement.tenant_id,
                        requirement=requirement,
                        resource=resource,
                        role=role,
                    )
                    for resource, role in self.participants()
                ]
            )
        return requirement


class PublishForm(forms.Form):
    effective_from = forms.DateField(label="Goes live on", widget=DATE_INPUT)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {"effective_from": timezone.localdate()})
        super().__init__(*args, **kwargs)


class ResourceForm(forms.Form):
    SLOT_FIELDS = ("unavailable", "preferred")
    KIND_FIELDS = {
        Resource.Kind.TEACHER: ("code", "name", "department", "max_load"),
        Resource.Kind.ROOM: ("code", "name", "department", "capacity", "tags"),
        Resource.Kind.SECTION: ("code", "name", "department", "capacity"),
        Resource.Kind.BATCH: ("code", "name", "department", "capacity", "parent"),
    }
    CAPACITY_LABELS = {
        Resource.Kind.ROOM: "Seats",
        Resource.Kind.SECTION: "Students",
        Resource.Kind.BATCH: "Students",
    }

    kind = forms.ChoiceField(choices=Resource.Kind.choices)
    code = forms.CharField(max_length=30, help_text="Short unique id, for example T01 or R101")
    name = forms.CharField(max_length=120, required=False, help_text="Optional full name")
    capacity = forms.IntegerField(min_value=0, initial=0)
    tags = forms.CharField(
        required=False,
        label="Room type tags",
        help_text="Comma separated, for example: lecture, lab",
    )
    max_load = forms.IntegerField(min_value=0, required=False, label="Max classes per week")

    def __init__(self, user, grid, *args, instance=None, **kwargs):
        self.grid = grid
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from(instance)
        super().__init__(*args, **kwargs)
        self.fields["department"] = department_field(user)
        self.fields["parent"] = forms.ModelChoiceField(
            visible(Resource.objects, user).filter(kind=Resource.Kind.SECTION, active=True),
            required=False,
            label="Belongs to section",
            empty_label="Choose a section",
        )
        choices = grids.slot_choices(grid)
        for name in self.SLOT_FIELDS:
            self.fields[name] = forms.MultipleChoiceField(
                choices=choices, required=False, widget=forms.CheckboxSelectMultiple
            )
        self.order_fields(
            ["kind", "code", "name", "department", "capacity", "tags", "max_load", "parent"]
        )
        self.fields["capacity"].label = self.CAPACITY_LABELS.get(self["kind"].value(), "Capacity")

    def initial_from(self, resource):
        return {
            "kind": resource.kind,
            "code": resource.code,
            "name": resource.name,
            "department": resource.department_id,
            "capacity": resource.capacity,
            "tags": ", ".join(resource.tags),
            "max_load": resource.max_load,
            "parent": resource.parent_id,
            "unavailable": grids.slot_values(resource.unavailable),
            "preferred": grids.slot_values(resource.preferred),
        }

    def split_fields(self):
        wanted = self.KIND_FIELDS.get(self["kind"].value())
        shown, tucked = [], [self["kind"]]
        for name in self.fields:
            if name == "kind" or name in self.SLOT_FIELDS:
                continue
            field = self[name]
            relevant = wanted is None or name in wanted or bool(field.errors)
            (shown if relevant else tucked).append(field)
        return shown, tucked

    @property
    def main_fields(self):
        return self.split_fields()[0]

    @property
    def tucked_fields(self):
        return self.split_fields()[1]

    @property
    def slots_open(self):
        return any(self[name].value() or self[name].errors for name in self.SLOT_FIELDS)

    def slot_rows(self, name):
        return grids.slot_rows(self.grid, self[name].value() or [])

    @property
    def unavailable_rows(self):
        return self.slot_rows("unavailable")

    @property
    def preferred_rows(self):
        return self.slot_rows("preferred")

    @property
    def period_labels(self):
        return grids.period_labels(self.grid)

    def clean_tags(self):
        return comma_list(self.cleaned_data["tags"])

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        if kind == Resource.Kind.BATCH and data.get("parent") is None:
            self.add_error("parent", "A batch needs its section")
        if kind != Resource.Kind.BATCH and data.get("parent") is not None:
            self.add_error("parent", "Only batches have a parent section")
        if kind == Resource.Kind.ROOM and not data.get("capacity"):
            self.add_error("capacity", "A room needs a capacity")
        if kind == Resource.Kind.TEACHER and data.get("max_load") is None:
            self.add_error("max_load", "A teacher needs a maximum load")
        return data

    def save(self):
        data = self.cleaned_data
        resource = self.instance or Resource()
        resource.kind = data["kind"]
        resource.code = data["code"]
        resource.name = data["name"]
        resource.department = data["department"]
        resource.capacity = data["capacity"]
        resource.tags = data["tags"]
        resource.max_load = data["max_load"] if data["kind"] == Resource.Kind.TEACHER else None
        resource.parent = data["parent"] if data["kind"] == Resource.Kind.BATCH else None
        resource.unavailable = [grids.parse_slot(v) for v in data["unavailable"]]
        resource.preferred = [grids.parse_slot(v) for v in data["preferred"]]
        resource.save()
        return resource


class SubjectForm(forms.Form):
    code = forms.CharField(max_length=30, help_text="Short code, for example CS301")
    name = forms.CharField(max_length=120)
    length = forms.IntegerField(
        min_value=1,
        max_value=4,
        initial=1,
        label="Periods per class",
        help_text="1 for a lecture, 2 or more for a lab that runs back to back",
    )

    def __init__(self, user, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {
                "code": instance.code,
                "name": instance.name,
                "length": instance.length,
                "department": instance.department_id,
            }
        super().__init__(*args, **kwargs)
        self.fields["department"] = department_field(user)
        self.order_fields(["code", "name", "length", "department"])

    def save(self):
        data = self.cleaned_data
        subject = self.instance or Subject()
        subject.code = data["code"]
        subject.name = data["name"]
        subject.length = data["length"]
        subject.department = data["department"]
        subject.save()
        return subject


class ImportForm(forms.Form):
    file = forms.FileField(label="Workbook (.xlsx)")
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        label="Check only, do not save yet (dry run)",
        label_suffix="",
    )

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Only .xlsx workbooks are accepted")
        if upload.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The workbook is larger than 5 MiB")
        return upload


class TimetableVersionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, version):
        return f"{version.timetable.name} v{version.number} ({version.status})"


class ExportForm(forms.Form):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["version"] = TimetableVersionChoiceField(
            visible(Version.objects, user)
            .select_related("timetable")
            .order_by("timetable__name", "-number"),
            label="Timetable",
            empty_label="Choose a timetable",
        )


class InviteForm(forms.Form):
    email = forms.EmailField()
    name = forms.CharField(max_length=150)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"] = forms.ModelChoiceField(
            Role.objects.all(), empty_label="Choose a role"
        )
        self.fields["department"] = department_field(user)
        self.order_fields(["email", "name", "role", "department"])


class DepartmentForm(forms.Form):
    name = forms.CharField(max_length=120, label="New department")

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Department.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This department already exists")
        return name


class RoleForm(forms.Form):
    name = forms.CharField(max_length=60)
    permissions = forms.MultipleChoiceField(
        choices=[(perm.value, PERM_LABELS[perm]) for perm in Perm],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = {"name": instance.name, "permissions": instance.permissions}
        super().__init__(*args, **kwargs)

    def save(self):
        role = self.instance or Role()
        role.name = self.cleaned_data["name"]
        role.permissions = sorted(self.cleaned_data["permissions"])
        role.save()
        return role
