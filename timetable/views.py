from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.audit import audit
from core.models import Department, Role, User
from core.perms import PERM_LABELS, Perm, PermissionedView, can, mfa_redirect
from timetable import grids, services
from timetable.forms import (
    XLSX_CONTENT_TYPE,
    DepartmentForm,
    DraftForm,
    ExportForm,
    ImportForm,
    InviteForm,
    PublishForm,
    RequirementForm,
    ResourceForm,
    RoleForm,
    SubjectForm,
    TimetableForm,
    visible,
)
from timetable.models import Assignment, Requirement, Resource, Subject, Timetable, Version

PANEL_ORDER = [
    ("timetables", Perm.TIMETABLE_VIEW),
    ("resources", Perm.RESOURCE_VIEW),
    ("subjects", Perm.SUBJECT_MANAGE),
    ("data", Perm.DATA_IMPORT),
    ("users", Perm.USER_MANAGE),
    ("roles", Perm.ROLE_MANAGE),
]
EDITABLE_STATUSES = frozenset({Version.Status.DRAFT, Version.Status.FAILED})
GENERATED_STATUSES = frozenset({Version.Status.DRAFT, Version.Status.PUBLISHED})
GRID_KINDS = {
    Resource.Kind.SECTION: "version-grid-section",
    Resource.Kind.TEACHER: "version-grid-teacher",
    Resource.Kind.ROOM: "version-grid-room",
}
KIND_PLURALS = {
    Resource.Kind.TEACHER: "Teachers",
    Resource.Kind.ROOM: "Rooms",
    Resource.Kind.SECTION: "Sections",
    Resource.Kind.BATCH: "Batches",
}


def is_planner(user):
    return bool(user.perms - {Perm.TIMETABLE_VIEW.value})


def admin_home(request):
    user = request.user
    if not user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    blocked = mfa_redirect(user)
    if blocked is not None:
        return blocked
    if is_planner(user):
        for panel, perm in PANEL_ORDER:
            if perm in user.perms:
                return redirect(f"panel-{panel}")
    if Perm.TIMETABLE_VIEW in user.perms:
        return redirect("my-timetable")
    raise PermissionDenied


def invites():
    from core import invites as module

    return module


def excel():
    from timetable import excel as module

    return module


def tenant_grid(request):
    configured = request.tenant.settings.get("default_grid")
    if configured:
        return configured
    latest = Timetable.objects.order_by("-created_at").values_list("grid", flat=True).first()
    return latest or grids.DEFAULT_GRID


def assignment_rows(version_ids):
    return list(
        Assignment.objects.filter(version_id__in=list(version_ids)).values(
            "version_id",
            "requirement_id",
            "session",
            "resource_id",
            "resource__kind",
            "resource__code",
            "resource__parent_id",
            "requirement__subject__code",
            "day",
            "period",
        )
    )


def versions_visible_to(user):
    return visible(Version.objects, user).select_related("timetable", "timetable__department")


def versions_owned_by(user):
    return Version.objects.owned_by(user).select_related("timetable")


@dataclass
class TimetableRow:
    timetable: object
    latest: object


@dataclass
class RequirementRow:
    requirement: object
    teachers: str
    attendees: str
    fixed_room: str
    fixed_slots: str


@dataclass
class ComparisonRow:
    key: str
    value: object


@dataclass
class ResourceLink:
    resource: object
    url: str


@dataclass
class SetupStep:
    label: str
    count: int
    url: str


def setup_steps(user, timetable_count):
    steps = []
    if Perm.RESOURCE_VIEW in user.perms:
        kinds = visible(Resource.objects, user).order_by().values_list("kind")
        counts = dict(kinds.annotate(Count("pk")))
        for kind in (Resource.Kind.TEACHER, Resource.Kind.ROOM, Resource.Kind.SECTION):
            url = f"{reverse('panel-resources')}?kind={kind}"
            steps.append(SetupStep(KIND_PLURALS[kind], counts.get(kind, 0), url))
    if Perm.SUBJECT_MANAGE in user.perms:
        count = visible(Subject.objects, user).count()
        steps.append(SetupStep("Subjects", count, reverse("panel-subjects")))
    url = f"{reverse('panel-timetables')}#new-timetable"
    steps.append(SetupStep("Timetables", timetable_count, url))
    return steps


class PanelView(PermissionedView):
    panel_name = None
    panel_template = None
    title = "Time-Table"

    def check_panel_access(self, request):
        if not is_planner(request.user):
            raise PermissionDenied

    def get(self, request, *args, **kwargs):
        self.check_panel_access(request)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.check_panel_access(request)
        return self.mutate(request, *args, **kwargs)

    def mutate(self, request, *args, **kwargs):
        raise Http404

    @property
    def is_hx(self):
        headers = self.request.headers
        restoring = headers.get("HX-History-Restore-Request") == "true"
        return headers.get("HX-Request") == "true" and not restoring

    def get_template_names(self):
        return [self.panel_template] if self.is_hx else ["admin.pug"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            panel_name=self.panel_name,
            panel_template=self.panel_template,
            title=self.title,
        )
        context.update(self.panel_context(**kwargs))
        return context

    def panel_context(self, **kwargs):
        return {}

    def panel_url(self):
        return reverse(f"panel-{self.panel_name}")

    def refreshed(self, url=None, notice=None, **context):
        url = url or self.panel_url()
        if self.is_hx:
            response = self.render_to_response(self.get_context_data(notice=notice, **context))
            response["HX-Push-Url"] = url
            return response
        if notice:
            messages.success(self.request, notice)
        return redirect(url)

    def render_panel(self, **context):
        return self.render_to_response(self.get_context_data(**context))


class TimetablesPanel(PanelView):
    permission = Perm.TIMETABLE_VIEW
    panel_name = "timetables"
    panel_template = "panels/timetables.pug"
    title = "Timetables"

    def panel_context(self, **kwargs):
        user = self.request.user
        timetables = (
            visible(Timetable.objects, user)
            .order_by("archived", "name")
            .select_related("department")
            .prefetch_related(
                Prefetch(
                    "versions",
                    queryset=Version.objects.order_by("-number"),
                    to_attr="latest_versions",
                )
            )
        )
        rows = [
            TimetableRow(timetable=t, latest=t.latest_versions[0] if t.latest_versions else None)
            for t in timetables
        ]
        manages = Perm.TIMETABLE_MANAGE in user.perms
        form = kwargs.get("form")
        if form is None and manages:
            form = TimetableForm(user)
        setup = setup_steps(user, len(rows)) if manages else []
        return {
            "rows": rows,
            "form": form,
            "setup": setup,
            "setup_pending": any(step.count == 0 for step in setup),
        }


class TimetableCreateView(TimetablesPanel):
    permission = Perm.TIMETABLE_MANAGE

    def mutate(self, request):
        form = TimetableForm(request.user, request.POST)
        if not form.is_valid():
            return self.render_panel(form=form)
        data = form.cleaned_data
        try:
            timetable = services.create_timetable(
                name=data["name"],
                department=data["department"],
                grid=form.grid(),
                start_date=data["start_date"],
                end_date=data["end_date"],
                actor=request.user,
            )
        except services.ServiceError as error:
            form.add_error(None, str(error))
            return self.render_panel(form=form)
        version = services.create_draft(timetable, actor=request.user)
        return redirect("version-detail", pk=version.pk)


class TimetableDetailView(PanelView):
    permission = Perm.TIMETABLE_VIEW
    panel_name = "timetables"
    panel_template = "timetable/timetable.pug"
    title = "Timetable"

    def queryset(self):
        return visible(Timetable.objects, self.request.user).select_related("department")

    def timetable(self):
        return get_object_or_404(self.queryset(), pk=self.kwargs["pk"])

    def panel_url(self):
        return reverse("timetable-detail", kwargs={"pk": self.kwargs["pk"]})

    def panel_context(self, **kwargs):
        user = self.request.user
        timetable = kwargs.get("timetable") or self.timetable()
        versions = list(
            Version.objects.filter(timetable=timetable).select_related("parent", "created_by")
        )
        manageable = can(user, Perm.TIMETABLE_MANAGE, timetable, write=True)
        form = kwargs.get("draft_form")
        if form is None and manageable:
            form = DraftForm(timetable)
        return {
            "timetable": timetable,
            "versions": versions,
            "manageable": manageable,
            "draft_form": form,
        }


class TimetableOwnedMixin:
    permission = Perm.TIMETABLE_MANAGE

    def queryset(self):
        return Timetable.objects.owned_by(self.request.user).select_related("department")


class VersionCreateView(TimetableOwnedMixin, TimetableDetailView):
    def mutate(self, request, pk):
        timetable = self.timetable()
        form = DraftForm(timetable, request.POST)
        if not form.is_valid():
            return self.render_panel(timetable=timetable, draft_form=form)
        try:
            version = services.create_draft(
                timetable,
                parent=form.cleaned_data["parent"],
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except services.ServiceError as error:
            form.add_error(None, str(error))
            return self.render_panel(timetable=timetable, draft_form=form)
        return redirect("version-detail", pk=version.pk)


class TimetableArchiveView(TimetableOwnedMixin, TimetableDetailView):
    def mutate(self, request, pk):
        with transaction.atomic():
            timetable = get_object_or_404(
                Timetable.objects.owned_by(request.user).select_for_update(), pk=pk
            )
            before = {"archived": timetable.archived}
            timetable.archived = not timetable.archived
            timetable.save(update_fields=["archived"])
            audit(
                request.user,
                "timetable.archive" if timetable.archived else "timetable.unarchive",
                timetable,
                before=before,
                after={"archived": timetable.archived},
            )
        return self.refreshed(timetable=timetable)


class VersionDetailView(PanelView):
    permission = Perm.TIMETABLE_VIEW
    panel_name = "timetables"
    panel_template = "timetable/version.pug"
    title = "Version"

    def queryset(self):
        return versions_visible_to(self.request.user)

    def version(self):
        return get_object_or_404(self.queryset(), pk=self.kwargs["pk"])

    def panel_url(self):
        return reverse("version-detail", kwargs={"pk": self.kwargs["pk"]})

    def requirement_rows(self, version):
        requirements = Requirement.objects.filter(version=version).select_related("subject")
        requirements = requirements.prefetch_related("participants__resource")
        rows = []
        for requirement in requirements:
            participants = list(requirement.participants.all())

            def codes(role, participants=participants):
                return ", ".join(sorted(p.resource.code for p in participants if p.role == role))

            rows.append(
                RequirementRow(
                    requirement=requirement,
                    teachers=codes("teacher"),
                    attendees=codes("attendee"),
                    fixed_room=codes("fixed_room"),
                    fixed_slots=grids.format_fixed_slots(requirement.fixed_slots, version.grid),
                )
            )
        return rows

    def resource_links(self, version, rows):
        resource_ids = {row["resource_id"] for row in rows}
        links = []
        for resource in Resource.objects.filter(pk__in=resource_ids).order_by("kind", "code"):
            name = GRID_KINDS.get(resource.kind)
            if name:
                links.append(
                    ResourceLink(
                        resource=resource,
                        url=reverse(name, kwargs={"pk": version.pk, "resource": resource.pk}),
                    )
                )
        return links

    def preview(self, version, links, rows):
        sections = [link for link in links if link.resource.kind == Resource.Kind.SECTION]
        chosen = (sections or links or [None])[0]
        if chosen is None:
            return None, None
        return chosen.resource, grids.build_grid(version.grid, rows, chosen.resource.pk)

    def panel_context(self, **kwargs):
        user = self.request.user
        version = kwargs.get("version") or self.version()
        timetable = version.timetable
        writable = can(user, Perm.TIMETABLE_MANAGE, timetable, write=True)
        editable = writable and version.status in EDITABLE_STATUSES
        form = kwargs.get("requirement_form")
        editing = kwargs.get("editing")
        if form is None and editable:
            form = RequirementForm(user, version)
        publish_form = kwargs.get("publish_form")
        can_publish = can(user, Perm.TIMETABLE_PUBLISH, timetable, write=True)
        if publish_form is None and can_publish:
            publish_form = PublishForm()
        rows = assignment_rows([version.pk])
        requirements = self.requirement_rows(version)
        links = self.resource_links(version, rows)
        generated = bool(links) and version.status in GENERATED_STATUSES
        placed = len({(row["requirement_id"], row["session"]) for row in rows})
        needed = sum(row.requirement.sessions for row in requirements)
        stale = generated and version.status == Version.Status.DRAFT and placed != needed
        preview_resource, preview_grid = self.preview(version, links if generated else [], rows)
        return {
            "version": version,
            "timetable": timetable,
            "requirements": requirements,
            "editable": editable,
            "can_generate": can(user, Perm.TIMETABLE_GENERATE, timetable, write=True)
            and version.status in EDITABLE_STATUSES,
            "can_reopen": writable and version.status == Version.Status.FAILED,
            "can_publish": can_publish and version.status == Version.Status.DRAFT,
            "requirement_form": form,
            "editing": editing,
            "publish_form": publish_form,
            "violations": kwargs.get("violations", []),
            "error": kwargs.get("error"),
            "others": Version.objects.filter(timetable=timetable).exclude(pk=version.pk),
            "resource_links": links,
            "generated": generated,
            "stale": stale,
            "ready": generated and not stale,
            "preview_resource": preview_resource,
            "grid": preview_grid,
        }


class VersionOwnedMixin:
    permission = Perm.TIMETABLE_MANAGE

    def queryset(self):
        return versions_owned_by(self.request.user)


def frozen_error(version):
    return f"Version v{version.number} is {version.status}; requirements are frozen"


class RequirementAddView(VersionOwnedMixin, VersionDetailView):
    def mutate(self, request, pk):
        version = self.version()
        if version.status not in EDITABLE_STATUSES:
            return self.render_panel(version=version, error=frozen_error(version))
        form = RequirementForm(request.user, version, request.POST)
        if not form.is_valid():
            return self.render_panel(version=version, requirement_form=form)
        requirement = form.save()
        audit(
            request.user,
            "requirement.add",
            requirement,
            after={"subject": requirement.subject.code},
        )
        return self.refreshed(version=version, notice="Requirement added")


class RequirementEditView(VersionOwnedMixin, VersionDetailView):
    def requirement(self):
        return get_object_or_404(
            Requirement.objects.owned_by(self.request.user).select_related("version__timetable"),
            pk=self.kwargs["pk"],
        )

    def panel_url(self):
        return reverse("version-detail", kwargs={"pk": self.requirement().version_id})

    def get(self, request, pk):
        self.check_panel_access(request)
        requirement = self.requirement()
        version = requirement.version
        form = RequirementForm(request.user, version, instance=requirement)
        return self.render_panel(version=version, requirement_form=form, editing=requirement)

    def mutate(self, request, pk):
        requirement = self.requirement()
        version = requirement.version
        if version.status not in EDITABLE_STATUSES:
            return self.render_panel(version=version, error=frozen_error(version))
        form = RequirementForm(request.user, version, request.POST, instance=requirement)
        if not form.is_valid():
            return self.render_panel(version=version, requirement_form=form, editing=requirement)
        form.save()
        requirement.assignments.all().delete()
        audit(
            request.user,
            "requirement.edit",
            requirement,
            after={"subject": requirement.subject.code},
        )
        return self.refreshed(
            reverse("version-detail", kwargs={"pk": version.pk}),
            version=version,
            notice="Requirement updated",
        )


class RequirementDeleteView(RequirementEditView):
    def get(self, request, pk):
        raise Http404

    def mutate(self, request, pk):
        requirement = self.requirement()
        version = requirement.version
        if version.status not in EDITABLE_STATUSES:
            return self.render_panel(version=version, error=frozen_error(version))
        before = {"subject": requirement.subject.code, "sessions": requirement.sessions}
        with transaction.atomic():
            audit(request.user, "requirement.delete", requirement, before=before)
            requirement.delete()
        return self.refreshed(
            reverse("version-detail", kwargs={"pk": version.pk}),
            version=version,
            notice="Requirement removed",
        )


class VersionSolveView(VersionOwnedMixin, VersionDetailView):
    permission = Perm.TIMETABLE_GENERATE

    def mutate(self, request, pk):
        version = self.version()
        try:
            services.start_solve(version, request.user)
        except services.ServiceError as error:
            return self.render_panel(version=version, error=str(error))
        version.refresh_from_db()
        solving = version.status == Version.Status.SOLVING
        notice = "Building the timetable. This page updates by itself." if solving else None
        return self.refreshed(version=version, notice=notice)


class VersionReopenView(VersionOwnedMixin, VersionDetailView):
    def mutate(self, request, pk):
        version = self.version()
        try:
            services.reopen(version, request.user)
        except services.ServiceError as error:
            return self.render_panel(version=version, error=str(error))
        version.refresh_from_db()
        return self.refreshed(version=version, notice="Version reopened")


class VersionPublishView(VersionOwnedMixin, VersionDetailView):
    permission = Perm.TIMETABLE_PUBLISH

    def mutate(self, request, pk):
        version = self.version()
        form = PublishForm(request.POST)
        if not form.is_valid():
            return self.render_panel(version=version, publish_form=form)
        try:
            services.publish(
                version, effective_from=form.cleaned_data["effective_from"], actor=request.user
            )
        except services.Conflict as error:
            return self.render_panel(
                version=version, publish_form=form, violations=error.violations
            )
        except services.ServiceError as error:
            return self.render_panel(version=version, publish_form=form, error=str(error))
        version.refresh_from_db()
        return self.refreshed(version=version, notice="Published")


class VersionStatusView(VersionDetailView):
    panel_template = "timetable/status.pug"

    def panel_context(self, **kwargs):
        return {"version": self.version()}

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        if self.is_hx and context["version"].status != Version.Status.SOLVING:
            response["HX-Refresh"] = "true"
        return response


def comparison_rows(output):
    if isinstance(output, dict):
        return [ComparisonRow(key=str(k), value=v) for k, v in output.items()]
    if isinstance(output, list | tuple | set | frozenset):
        return [ComparisonRow(key=str(i + 1), value=v) for i, v in enumerate(output)]
    return [ComparisonRow(key="result", value=output)]


def resource_for(resource_id):
    if not resource_id:
        return None
    try:
        return Resource.objects.filter(pk=resource_id).first()
    except (ValueError, ValidationError):
        return None


def first_section(rows):
    for row in sorted(rows, key=lambda r: (r["resource__kind"], r["resource__code"])):
        if row["resource__kind"] == Resource.Kind.SECTION:
            return row["resource_id"]
    return rows[0]["resource_id"] if rows else None


class VersionCompareView(VersionDetailView):
    panel_template = "timetable/compare.pug"
    title = "Compare versions"

    def panel_url(self):
        return self.request.get_full_path()

    def panel_context(self, **kwargs):
        version = self.version()
        other = get_object_or_404(
            self.queryset().filter(timetable=version.timetable), pk=self.request.GET.get("other")
        )
        rows = assignment_rows([version.pk, other.pk])
        resource = resource_for(self.request.GET.get("resource") or first_section(rows))
        resource_id = resource.pk if resource else None
        left = grids.build_grid(
            version.grid, [r for r in rows if r["version_id"] == version.pk], resource_id
        )
        right = grids.build_grid(
            other.grid, [r for r in rows if r["version_id"] == other.pk], resource_id
        )
        grids.mark_changes(left, right)
        choices = Resource.objects.filter(pk__in={r["resource_id"] for r in rows}).order_by(
            "kind", "code"
        )
        return {
            "version": version,
            "other": other,
            "timetable": version.timetable,
            "resource": resource,
            "resource_pk": resource_id,
            "resources": choices,
            "left": left,
            "right": right,
            "comparison": comparison_rows(services.compare(version, other)),
        }


class GridView(VersionDetailView):
    panel_template = "timetable/grid.pug"
    kind = None

    def panel_url(self):
        return self.request.path

    def panel_context(self, **kwargs):
        version = self.version()
        resource = get_object_or_404(
            Resource.objects.filter(kind=self.kind), pk=self.kwargs["resource"]
        )
        grid = grids.build_grid(version.grid, assignment_rows([version.pk]), resource.pk)
        return {
            "version": version,
            "timetable": version.timetable,
            "resource": resource,
            "grid": grid,
        }


class ResourcesPanel(PanelView):
    permission = Perm.RESOURCE_VIEW
    panel_name = "resources"
    panel_template = "panels/resources.pug"
    title = "Teachers & Rooms"

    def kind(self):
        requested = self.request.GET.get("kind") or self.request.POST.get("kind")
        return requested if requested in Resource.Kind.values else Resource.Kind.TEACHER

    def panel_url(self):
        return f"{reverse('panel-resources')}?kind={self.kind()}"

    def panel_context(self, **kwargs):
        user = self.request.user
        kind = self.kind()
        resources = list(
            visible(Resource.objects, user)
            .filter(kind=kind)
            .select_related("department", "parent")
            .order_by("-active", "code")
        )
        for resource in resources:
            resource.editable = can(user, Perm.RESOURCE_MANAGE, resource, write=True)
        form = kwargs.get("form")
        if form is None and Perm.RESOURCE_MANAGE in user.perms:
            form = ResourceForm(user, tenant_grid(self.request), initial={"kind": kind})
        return {
            "kind": kind,
            "kinds": list(KIND_PLURALS.items()),
            "resources": resources,
            "form": form,
            "editing": kwargs.get("editing"),
        }


class ResourceCreateView(ResourcesPanel):
    permission = Perm.RESOURCE_MANAGE

    def mutate(self, request):
        form = ResourceForm(request.user, tenant_grid(request), request.POST)
        if not form.is_valid():
            return self.render_panel(form=form)
        resource = form.save()
        audit(request.user, "resource.create", resource, after={"code": resource.code})
        return self.refreshed(notice=f"{resource.code} created")


class ResourceEditView(ResourcesPanel):
    permission = Perm.RESOURCE_MANAGE

    def resource(self, for_update=False):
        queryset = Resource.objects.owned_by(self.request.user)
        if for_update:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def kind(self):
        return self.resource().kind

    def get(self, request, pk):
        self.check_panel_access(request)
        resource = self.resource()
        form = ResourceForm(request.user, tenant_grid(request), instance=resource)
        return self.render_panel(form=form, editing=resource)

    def mutate(self, request, pk):
        resource = self.resource()
        form = ResourceForm(request.user, tenant_grid(request), request.POST, instance=resource)
        if not form.is_valid():
            return self.render_panel(form=form, editing=resource)
        before = {"code": resource.code, "kind": resource.kind}
        form.save()
        audit(request.user, "resource.edit", resource, before=before, after={"code": resource.code})
        return self.refreshed(notice=f"{resource.code} updated")


class ResourceToggleView(ResourceEditView):
    def get(self, request, pk):
        raise Http404

    def mutate(self, request, pk):
        with transaction.atomic():
            resource = self.resource(for_update=True)
            before = {"active": resource.active}
            resource.active = not resource.active
            resource.save(update_fields=["active"])
            audit(
                request.user,
                "resource.toggle",
                resource,
                before=before,
                after={"active": resource.active},
            )
        return self.refreshed(f"{reverse('panel-resources')}?kind={resource.kind}")


class SubjectsPanel(PanelView):
    permission = Perm.SUBJECT_MANAGE
    panel_name = "subjects"
    panel_template = "panels/subjects.pug"
    title = "Subjects"

    def panel_context(self, **kwargs):
        user = self.request.user
        form = kwargs.get("form") or SubjectForm(user)
        subjects = list(
            visible(Subject.objects, user).select_related("department").order_by("-active", "code")
        )
        for subject in subjects:
            subject.editable = can(user, Perm.SUBJECT_MANAGE, subject, write=True)
        return {
            "subjects": subjects,
            "form": form,
            "editing": kwargs.get("editing"),
        }


class SubjectCreateView(SubjectsPanel):
    def mutate(self, request):
        form = SubjectForm(request.user, request.POST)
        if not form.is_valid():
            return self.render_panel(form=form)
        subject = form.save()
        audit(request.user, "subject.create", subject, after={"code": subject.code})
        return self.refreshed(notice=f"{subject.code} created")


class SubjectEditView(SubjectsPanel):
    def subject(self, for_update=False):
        queryset = Subject.objects.owned_by(self.request.user)
        if for_update:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=self.kwargs["pk"])

    def get(self, request, pk):
        self.check_panel_access(request)
        subject = self.subject()
        return self.render_panel(form=SubjectForm(request.user, instance=subject), editing=subject)

    def mutate(self, request, pk):
        subject = self.subject()
        form = SubjectForm(request.user, request.POST, instance=subject)
        if not form.is_valid():
            return self.render_panel(form=form, editing=subject)
        before = {"code": subject.code}
        form.save()
        audit(request.user, "subject.edit", subject, before=before, after={"code": subject.code})
        return self.refreshed(notice=f"{subject.code} updated")


class SubjectToggleView(SubjectEditView):
    def get(self, request, pk):
        raise Http404

    def mutate(self, request, pk):
        with transaction.atomic():
            subject = self.subject(for_update=True)
            before = {"active": subject.active}
            subject.active = not subject.active
            subject.save(update_fields=["active"])
            audit(
                request.user,
                "subject.toggle",
                subject,
                before=before,
                after={"active": subject.active},
            )
        return self.refreshed()


class DataPanel(PanelView):
    permission = Perm.DATA_IMPORT
    panel_name = "data"
    panel_template = "panels/data.pug"
    title = "Import / Export"

    def panel_context(self, **kwargs):
        user = self.request.user
        export_form = kwargs.get("export_form")
        if export_form is None and Perm.DATA_EXPORT in user.perms:
            export_form = ExportForm(user)
        summary = kwargs.get("summary") or {}
        return {
            "import_form": kwargs.get("import_form") or ImportForm(),
            "export_form": export_form,
            "plan": kwargs.get("plan"),
            "summary": {key: value for key, value in summary.items() if not key.endswith("_id")},
            "imported_version": summary.get("version_id"),
            "applied": kwargs.get("applied", False),
        }


class DataImportView(DataPanel):
    def mutate(self, request):
        form = ImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_panel(import_form=form)
        plan = excel().parse_workbook(form.cleaned_data["file"].read())
        if form.cleaned_data["dry_run"] or plan.errors:
            return self.render_panel(import_form=form, plan=plan, summary=plan.summary)
        summary = excel().apply(plan, request.user)
        audit(request.user, "data.import", after={"summary": summary})
        return self.render_panel(plan=plan, summary=summary, applied=True)


class DataSampleView(DataPanel):
    def get(self, request):
        self.check_panel_access(request)
        response = HttpResponse(excel().sample_workbook(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = content_disposition_header(True, "timetable-sample.xlsx")
        return response


class DataExportView(DataPanel):
    permission = Perm.DATA_EXPORT

    def mutate(self, request):
        form = ExportForm(request.user, request.POST)
        if not form.is_valid():
            return self.render_panel(export_form=form)
        version = form.cleaned_data["version"]
        payload = excel().export_version(version)
        audit(request.user, "data.export", version)
        response = HttpResponse(payload, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = content_disposition_header(
            True, f"timetable-v{version.number}.xlsx"
        )
        return response


def users_visible_to(user):
    queryset = User.objects.select_related("role", "department")
    if user.department_id is None:
        return queryset
    return queryset.filter(department_id=user.department_id)


class UsersPanel(PanelView):
    permission = Perm.USER_MANAGE
    panel_name = "users"
    panel_template = "panels/users.pug"
    title = "Users"

    def panel_context(self, **kwargs):
        user = self.request.user
        unscoped = user.department_id is None
        department_form = kwargs.get("department_form")
        if department_form is None and unscoped:
            department_form = DepartmentForm()
        return {
            "users": users_visible_to(user),
            "form": kwargs.get("form") or InviteForm(user),
            "error": kwargs.get("error"),
            "departments": Department.objects.all() if unscoped else [],
            "department_form": department_form,
        }

    def target(self, for_update=False):
        queryset = users_visible_to(self.request.user)
        if for_update:
            queryset = User.objects.filter(pk__in=queryset.values("pk")).select_for_update()
        return get_object_or_404(queryset, pk=self.kwargs["pk"])


class UserInviteView(UsersPanel):
    def mutate(self, request):
        form = InviteForm(request.user, request.POST)
        if not form.is_valid():
            return self.render_panel(form=form)
        data = form.cleaned_data
        invited = invites().invite_user(
            email=data["email"],
            name=data["name"],
            role=data["role"],
            department=data["department"],
            actor=request.user,
        )
        audit(
            request.user,
            "user.invite",
            invited if isinstance(invited, User) else None,
            after={"email": data["email"], "role": data["role"].name},
        )
        return self.refreshed(notice="Invitation sent")


class DepartmentCreateView(UsersPanel):
    def mutate(self, request):
        if request.user.department_id is not None:
            raise PermissionDenied
        form = DepartmentForm(request.POST)
        if not form.is_valid():
            return self.render_panel(department_form=form)
        department = Department.objects.create(name=form.cleaned_data["name"])
        audit(request.user, "department.create", department, after={"name": department.name})
        return self.refreshed(notice=f"Department {department.name} added")


class UserToggleView(UsersPanel):
    def mutate(self, request, pk):
        with transaction.atomic():
            target = self.target(for_update=True)
            if target.pk == request.user.pk:
                return self.render_panel(error="You cannot deactivate your own account")
            before = {"is_active": target.is_active}
            target.is_active = not target.is_active
            target.auth_version += 1
            target.save(update_fields=["is_active", "auth_version"])
            audit(
                request.user,
                "user.activate" if target.is_active else "user.deactivate",
                target,
                before=before,
                after={"is_active": target.is_active},
            )
        return self.refreshed()


class UserResendInviteView(UsersPanel):
    def mutate(self, request, pk):
        target = self.target()
        if target.has_usable_password():
            return self.render_panel(error="That user has already set a password")
        invites().resend_invite(request.user, target)
        audit(request.user, "user.invite.resend", target, after={"email": target.email})
        return self.refreshed(notice="Invitation re-sent")


class UserResetMfaView(UsersPanel):
    def mutate(self, request, pk):
        with transaction.atomic():
            target = self.target(for_update=True)
            removed, _ = TOTPDevice.objects.filter(user=target).delete()
            target.auth_version += 1
            target.save(update_fields=["auth_version"])
            audit(request.user, "user.mfa.reset", target, after={"devices_removed": removed})
        return self.refreshed(notice="MFA reset")


class RolesPanel(PanelView):
    permission = Perm.ROLE_MANAGE
    panel_name = "roles"
    panel_template = "panels/roles.pug"
    title = "Roles"

    def panel_context(self, **kwargs):
        roles = list(Role.objects.annotate(user_count=Count("user")))
        for role in roles:
            role.labels = [PERM_LABELS.get(code, code) for code in role.permissions]
        return {
            "roles": roles,
            "form": kwargs.get("form") or RoleForm(),
            "editing": kwargs.get("editing"),
            "error": kwargs.get("error"),
        }

    def role(self, for_update=False):
        queryset = Role.objects.all()
        if for_update:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=self.kwargs["pk"])


class RoleCreateView(RolesPanel):
    def mutate(self, request):
        form = RoleForm(request.POST)
        if not form.is_valid():
            return self.render_panel(form=form)
        role = form.save()
        audit(request.user, "role.create", role, after={"permissions": role.permissions})
        return self.refreshed(notice=f"Role {role.name} created")


class RoleEditView(RolesPanel):
    def get(self, request, pk):
        self.check_panel_access(request)
        role = self.role()
        return self.render_panel(form=RoleForm(instance=role), editing=role)

    def mutate(self, request, pk):
        role = self.role()
        form = RoleForm(request.POST, instance=role)
        if not form.is_valid():
            return self.render_panel(form=form, editing=role)
        before = {"permissions": role.permissions}
        form.save()
        audit(
            request.user, "role.edit", role, before=before, after={"permissions": role.permissions}
        )
        return self.refreshed(notice=f"Role {role.name} updated")


class RoleDeleteView(RolesPanel):
    def mutate(self, request, pk):
        with transaction.atomic():
            role = self.role(for_update=True)
            if User.objects.filter(role=role).exists():
                return self.render_panel(error=f"Role {role.name} is still assigned to users")
            before = {"name": role.name, "permissions": role.permissions}
            role.delete()
            audit(request.user, "role.delete", role, before=before)
        return self.refreshed(notice="Role deleted")


class MyTimetableView(PermissionedView):
    permission = Perm.TIMETABLE_VIEW
    template_name = "timetable/my.pug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = Resource.objects.filter(
            user=self.request.user, kind=Resource.Kind.TEACHER
        ).first()
        grid = None
        if teacher is not None:
            today = timezone.localdate()
            versions = [
                version
                for version in (
                    services.active_version(timetable, today)
                    for timetable in Timetable.objects.filter(archived=False)
                )
                if version is not None
            ]
            layout = versions[0].grid if versions else grids.DEFAULT_GRID
            grid = grids.build_grid(layout, assignment_rows([v.pk for v in versions]), teacher.pk)
        context.update(title="My timetable", teacher=teacher, grid=grid)
        return context
