import re

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import Department, Role
from core.perms import Perm
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
    name = forms.CharField(max_length=120)
    days = forms.MultipleChoiceField(
        choices=[(day, day) for day in DAYS],
        widget=forms.CheckboxSelectMultiple,
        initial=DAYS[:6],
    )
    periods = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
        initial="\n".join(f"{start}-{end}" for start, end in grids.DEFAULT_GRID["periods"]),
        help_text="One HH:MM-HH:MM per line",
    )
    breaks_after = forms.CharField(
        required=False,
        initial="4",
        help_text="Period numbers followed by a break, comma separated",
    )
    start_date = forms.DateField(widget=DATE_INPUT)
    end_date = forms.DateField(widget=DATE_INPUT)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"] = department_field(user)
        self.order_fields(
            ["name", "department", "days", "periods", "breaks_after", "start_date", "end_date"]
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
        return f"v{version.number} ({version.status})"


class DraftForm(forms.Form):
    reason = forms.CharField(required=False, max_length=400)

    def __init__(self, timetable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"] = VersionChoiceField(
            Version.objects.filter(timetable=timetable).order_by("-number"),
            required=False,
            empty_label="Start empty",
        )
        self.order_fields(["parent", "reason"])


class RequirementForm(forms.Form):
    sessions = forms.IntegerField(min_value=1, max_value=40, initial=1)
    length = forms.IntegerField(
        min_value=1, max_value=4, required=False, help_text="Defaults to the subject length"
    )
    room_tag = forms.CharField(max_length=30, required=False)
    rooms_needed = forms.IntegerField(min_value=0, max_value=8, initial=1)
    fixed_slots = forms.CharField(
        required=False, help_text="For example 'Mon 1, Tue 3' (day and period number)"
    )

    def __init__(self, user, version, *args, instance=None, **kwargs):
        self.version = version
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = self.initial_from(instance)
        super().__init__(*args, **kwargs)
        resources = visible(Resource.objects, user).filter(active=True)
        self.fields["subject"] = forms.ModelChoiceField(
            visible(Subject.objects, user).filter(active=True)
        )
        self.fields["teachers"] = forms.ModelMultipleChoiceField(
            resources.filter(kind=Resource.Kind.TEACHER)
        )
        self.fields["attendees"] = forms.ModelMultipleChoiceField(
            resources.filter(kind__in=[Resource.Kind.SECTION, Resource.Kind.BATCH])
        )
        self.fields["fixed_room"] = forms.ModelChoiceField(
            resources.filter(kind=Resource.Kind.ROOM), required=False
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
    effective_from = forms.DateField(widget=DATE_INPUT)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {"effective_from": timezone.localdate()})
        super().__init__(*args, **kwargs)


class ResourceForm(forms.Form):
    SLOT_FIELDS = ("unavailable", "preferred")

    kind = forms.ChoiceField(choices=Resource.Kind.choices)
    code = forms.CharField(max_length=30)
    name = forms.CharField(max_length=120, required=False)
    capacity = forms.IntegerField(
        min_value=0, initial=0, help_text="Room capacity or section strength"
    )
    tags = forms.CharField(required=False, help_text="Comma separated")
    max_load = forms.IntegerField(min_value=0, required=False, help_text="Teachers only")

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
            help_text="Batches only: the section the batch belongs to",
        )
        choices = grids.slot_choices(grid)
        for name in self.SLOT_FIELDS:
            self.fields[name] = forms.MultipleChoiceField(
                choices=choices, required=False, widget=forms.CheckboxSelectMultiple
            )
        self.order_fields(
            ["kind", "code", "name", "department", "capacity", "tags", "max_load", "parent"]
        )

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

    @property
    def main_fields(self):
        return [self[name] for name in self.fields if name not in self.SLOT_FIELDS]

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
    code = forms.CharField(max_length=30)
    name = forms.CharField(max_length=120)
    length = forms.IntegerField(min_value=1, max_value=4, initial=1)

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
    dry_run = forms.BooleanField(required=False, initial=True, label="Dry run (validate only)")

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
            .order_by("timetable__name", "-number")
        )


class InviteForm(forms.Form):
    email = forms.EmailField()
    name = forms.CharField(max_length=150)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"] = forms.ModelChoiceField(Role.objects.all())
        self.fields["department"] = department_field(user)
        self.order_fields(["email", "name", "role", "department"])


class RoleForm(forms.Form):
    name = forms.CharField(max_length=60)
    permissions = forms.MultipleChoiceField(
        choices=[(perm.value, perm.value) for perm in Perm],
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
