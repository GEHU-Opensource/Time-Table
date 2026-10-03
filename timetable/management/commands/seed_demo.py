from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Department, Tenant
from core.tenancy import tenant_scope
from timetable import services
from timetable.models import Requirement, RequirementResource, Resource, Subject, Timetable

GRID = {
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "periods": [
        ["09:00", "09:55"],
        ["09:55", "10:50"],
        ["11:10", "12:05"],
        ["12:05", "13:00"],
        ["13:20", "14:15"],
        ["14:15", "15:10"],
        ["15:30", "16:25"],
    ],
    "breaks_after": [1, 3, 5],
}

TEACHERS = [
    ("T01", "Dr. Pant"),
    ("T02", "Chauhan"),
    ("T03", "Singh"),
    ("T04", "Bisht"),
    ("T05", "Negi"),
    ("T06", "Rawat"),
]
ROOMS = [
    ("R1", 80, ["lecture"]),
    ("R2", 80, ["lecture", "projector"]),
    ("L1", 35, ["lab"]),
    ("L2", 35, ["lab"]),
]
SUBJECTS = [
    ("OS", "Operating Systems", 1),
    ("DBMS", "Database Systems", 1),
    ("MATH", "Discrete Mathematics", 1),
    ("CN", "Computer Networks", 1),
    ("DBMS-LAB", "Database Lab", 2),
    ("CN-LAB", "Networks Lab", 2),
]
PLAN = [
    ("OS", "T01", 4, "lecture"),
    ("DBMS", "T02", 3, "lecture"),
    ("MATH", "T04", 4, "lecture"),
    ("CN", "T03", 3, "lecture"),
]
LABS = [("DBMS-LAB", "T02"), ("CN-LAB", "T03")]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(slug=options["tenant"]).first()
        if tenant is None:
            raise CommandError(f"no tenant with slug {options['tenant']}")
        with tenant_scope(tenant.id):
            if Timetable.objects.filter(name="B.Tech CSE Sem 5").exists():
                self.stdout.write("demo data already present")
                return
            department, _ = Department.objects.get_or_create(name="CSE")
            teachers = {
                code: Resource.objects.create(
                    kind="teacher", code=code, name=name, max_load=18, department=department
                )
                for code, name in TEACHERS
            }
            for code, capacity, tags in ROOMS:
                Resource.objects.create(kind="room", code=code, capacity=capacity, tags=tags)
            subjects = {
                code: Subject.objects.create(
                    code=code, name=name, length=length, department=department
                )
                for code, name, length in SUBJECTS
            }
            sections = []
            for label, strength in (("A", 70), ("B", 68)):
                section = Resource.objects.create(
                    kind="section", code=f"CSE-5{label}", capacity=strength, department=department
                )
                batches = [
                    Resource.objects.create(
                        kind="batch",
                        code=f"CSE-5{label}-G{index}",
                        capacity=strength // 2 + strength % 2,
                        parent=section,
                        department=department,
                    )
                    for index in (1, 2)
                ]
                sections.append((section, batches))
            today = timezone.localdate()
            timetable = services.create_timetable(
                name="B.Tech CSE Sem 5",
                department=department,
                grid=GRID,
                start_date=today - timedelta(days=7),
                end_date=today + timedelta(days=120),
                actor=None,
            )
            draft = services.create_draft(timetable, reason="Demo data", actor=None)
            for section, batches in sections:
                for subject, teacher, sessions, tag in PLAN:
                    requirement = Requirement.objects.create(
                        version=draft,
                        subject=subjects[subject],
                        sessions=sessions,
                        length=1,
                        room_tag=tag,
                        rooms_needed=1,
                    )
                    RequirementResource.objects.create(
                        requirement=requirement, resource=teachers[teacher], role="teacher"
                    )
                    RequirementResource.objects.create(
                        requirement=requirement, resource=section, role="attendee"
                    )
                for subject, teacher in LABS:
                    requirement = Requirement.objects.create(
                        version=draft,
                        subject=subjects[subject],
                        sessions=1,
                        length=2,
                        room_tag="lab",
                        rooms_needed=2,
                    )
                    RequirementResource.objects.create(
                        requirement=requirement, resource=teachers[teacher], role="teacher"
                    )
                    for batch in batches:
                        RequirementResource.objects.create(
                            requirement=requirement, resource=batch, role="attendee"
                        )
            self.stdout.write(f"seeded demo data: timetable {timetable.pk}, draft v{draft.number}")
