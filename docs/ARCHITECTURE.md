# Architecture

Time-Table is one Django 5.2 project that serves many universities (tenants) from one
PostgreSQL database. Each tenant lives on its own subdomain of `BASE_DOMAIN`, every table that
holds tenant data carries a `tenant_id`, and PostgreSQL row-level security enforces the
boundary beneath the ORM. Timetables are solved by OR-Tools CP-SAT in a background worker and
published as immutable versions whose assignments feed a `is_live` occupancy index.

## Modules

| Package | Responsibility | May import |
|---|---|---|
| `solver/` | Pure-Python CP-SAT model, independent validator and the dataclasses in `solver/types.py`. No Django. | standard library, `ortools` |
| `core/` | Tenancy (`core/tenancy.py`), users, roles, permissions (`core/perms.py`), audit (`core/audit.py`), authentication, invites, MFA, health endpoint, management commands, JSON logging, deploy checks. | Django, `solver` |
| `timetable/` | Resources, subjects, timetables, versions, requirements, assignments; the service layer (`timetable/services.py`), procrastinate tasks, import/export, panels and grids. | Django, `core`, `solver` |
| `config/` | Settings read from the environment, URL root, WSGI entry. | everything |
| `templates/` | Pug templates compiled by pypugjs into Django templates. | |
| `static/` | One stylesheet and a vendored htmx. | |
| `deploy/` | Dockerfiles, Compose stack, Caddyfile, entrypoint, database roles. | |
| `scripts/` | Repository lint scripts run by CI and by `tests/test_no_comments.py`. | |

`import-linter` (configured in `pyproject.toml`) enforces that `solver` imports no Django and
`core` never imports `timetable`.

## Request flow

1. Caddy terminates TLS for `*.BASE_DOMAIN`, limits request bodies to 6 MB, strips the
   `Server` header, adds `X-Request-ID` from its own request UUID and proxies to `web:8000`.
2. gunicorn hands the request to Django. `SecurityMiddleware` enforces HTTPS, HSTS and the
   other response headers; `WhiteNoiseMiddleware` serves hashed static files.
3. Sessions, CSRF (stored in the session, not a cookie), authentication and `django-otp`
   middleware run next.
4. `core.tenancy.TenantMiddleware`:
   - stores `X-Request-ID` (or a fresh UUID) in the `request_id` context variable so every
     log line and audit event carries it;
   - lets `/healthz/` through without a tenant;
   - derives the tenant slug from the host (`<slug>.<BASE_DOMAIN>`, one label only), loads an
     unarchived `Tenant` or answers 404;
   - opens `tenant_scope(tenant.id)`: sets the `tenant_id` context variable and, inside one
     database transaction, runs `SELECT set_config('app.tenant_id', <uuid>, true)`. That
     transaction-local GUC is what the RLS policies read through `app_tenant_id()`;
   - logs out and answers 403 if the session's user belongs to a different tenant.
5. Views subclass `core.perms.PermissionedView`. The view declares a permission code; the
   base class redirects anonymous users to login, forces MFA for users holding a privileged
   permission, and raises 403 when the role lacks the code. Object-level checks use
   `can(user, perm, obj, write=True)`, which confines department-scoped users to objects of
   their own department (and lets them read tenant-wide objects with `department=None`).
6. `Model.objects` is a `TenantManager`: it filters by the context tenant and raises
   `TenantUnset` outside a scope. `TenantModel.save()` fills `tenant_id` from the context and
   refuses cross-tenant writes. RLS repeats the same filter in the database for the `tt_app`
   and `tt_worker` roles, which cannot bypass it (`FORCE ROW LEVEL SECURITY`).
7. Templates are Pug. htmx drives panel swaps; the CSRF token is set once on `<body>` through
   `hx-headers`, and the CSP permits scripts only from self with a nonce.

## Solve flow

```
browser --POST start--> web (service start_solve)
    checks permission and rate limit (SOLVES_PER_TENANT_PER_HOUR)
    SELECT ... FOR UPDATE on the Version, draft/failed -> solving
    defers procrastinate task run_solve(version_id, tenant_id)
worker --picks task--> tenant_scope(tenant_id)
    build_instance(version) -> solver.types.Instance
        resources, requirements, grid, blocked slots from other live timetables, hints from parent
    sandbox: subprocess with RLIMIT_AS = SOLVER_MEMORY_BYTES, wall clock = max_seconds,
             model size capped by SOLVER_MAX_MODEL_SIZE
    solver.solve(instance) -> Result(status, placements, unplaced, reasons, stats)
    solver.validate(instance, placements) re-checks every hard rule independently
    apply_result(version, result)
        deletes old Assignment rows of the version, bulk_creates new rows with tenant_id set,
        one row per (requirement, session, resource, day, period); batch rows carry `serves`
        solving -> draft (solved) or solving -> failed (infeasible, unknown, too large)
reset_stale_solving(now) returns versions stuck in `solving` past STALE_SOLVE_GRACE to failed
```

The database trigger `assignment_guard` only permits inserts while a version is `draft` or
`solving`, and never with `is_live = true`.

## Publish flow

```
publish(version, effective_from, actor)
    pg_advisory_xact_lock(hash(tenant_id, timetable_id))
    SELECT ... FOR UPDATE on the version; must be draft with assignments
    validator re-run against live rows of other timetables (blocked slots)
    status -> published, effective_from, published_at
    flip_live(on=today) for the timetable:
        UPDATE assignments SET is_live = false WHERE timetable's versions
        UPDATE assignments SET is_live = true WHERE version = active_version(timetable, today)
    audit("version.publish", ...)
```

The partial unique index `assignment_live_slot_unique (tenant, resource, day, period) WHERE
is_live` makes a double booking across live timetables impossible to commit, whatever the
solver or validator did. The trigger `version_guard` makes published versions immutable and
only allows `is_live` to change on published assignments.

## Versioning semantics

- A `Timetable` is a named container with a grid, a date range and an optional department.
- A `Version` has a sequential `number`, an optional `parent`, a `status` (`draft`, `solving`,
  `failed`, `published`), its own copy of the grid, and `effective_from` once published.
- Status transitions permitted by the trigger: draft -> solving | published;
  solving -> draft | failed; failed -> draft | solving. Published is terminal.
- `active_version(timetable, on)` is the published version with the greatest
  `effective_from <= on`. Several published versions can coexist with different
  `effective_from` dates (unique per date); `flip_live` runs daily and at publish time so
  `is_live` always reflects today's active version.
- Requirements and participants are frozen once a version leaves `draft`/`failed`
  (`requirement_guard`, `requirement_resource_guard`). A re-solve creates a child draft via
  `create_draft(parent=...)`, copies requirements, and passes the parent's placements as hints
  so the solver changes as little as possible.
- Versions and timetables are never deleted (`forbid_change` triggers); they are archived.

## Data model

Twelve tables (plus Django's sessions, otp, axes and procrastinate tables). Every tenant table
has `tenant_id`, a `UNIQUE (tenant_id, id)` constraint so other tables can reference it with a
composite foreign key `(tenant_id, <fk>) -> (tenant_id, id)`, and RLS policies `tenant_rw`
(for `tenant_id = app_tenant_id()`) and `ops_read` (read-only for `tt_ops`).

| Table | Purpose | Notable constraints, indexes, triggers |
|---|---|---|
| `core_tenant` | University; `slug` is the subdomain; `settings` JSON; `archived`. | RLS: anyone may read, update only own row. |
| `core_department` | Department inside a tenant. | `UNIQUE (tenant, name)`. |
| `core_role` | Named permission set (`permissions` text[]). | `CHECK permissions <@ known codes`; `UNIQUE (tenant, name)`. |
| `core_user` | Staff account: email, name, role, department, `auth_version`, invite token hash and expiry. | `UNIQUE (tenant, email)`; composite FKs to role and department; sessions invalidated when `auth_version` changes. |
| `core_auditevent` | Append-only audit log with hashed personal fields, `request_id`. | `REVOKE UPDATE, DELETE` from app roles; `forbid_change` trigger; composite FK actor; index `(tenant, created_at)`. |
| `timetable_resource` | Teacher, room, section or batch; capacity, tags, `max_load`, `unavailable` and `preferred` slot lists, `parent` for batches, optional link to a user. | `UNIQUE (tenant, kind, code)`; checks: batch has parent, room has capacity, teacher has max_load; composite FKs department, parent, user; no DELETE for app roles. |
| `timetable_subject` | Subject code, name, default `length` 1-4. | `UNIQUE (tenant, code)`; `CHECK length BETWEEN 1 AND 4`; no DELETE for app roles. |
| `timetable_timetable` | Timetable container: grid JSON, `start_date <= end_date`, department, archived. | `UNIQUE (tenant, name)`; `forbid_change` on DELETE; composite FK department. |
| `timetable_version` | Numbered version with status, grid, `effective_from`, `published_at`, `reason`, `solver_stats`, `parent`, `created_by`. | `UNIQUE (timetable, number)`; one published per `(timetable, effective_from)`; one `solving` per timetable; published implies `effective_from`; `version_guard` trigger; `forbid_change` on DELETE; composite FKs timetable, parent, creator. |
| `timetable_requirement` | What a version must schedule: subject, sessions per week, length, room tag, rooms needed, fixed slots. | checks sessions >= 1, length 1-4, rooms_needed <= 8; `requirement_guard` freezes outside draft/failed; composite FKs version, subject. |
| `timetable_requirementresource` | Participants of a requirement: teacher, attendee (section or batch) or fixed room. | `UNIQUE (requirement, resource)`; `requirement_resource_guard`; composite FKs requirement, resource. |
| `timetable_assignment` | One occupancy row per resource per period: version, requirement, session, resource, day, period, `serves` (the section a batch row stands in for), `is_live`. | `UNIQUE (version, resource, day, period)`; partial `UNIQUE (tenant, resource, day, period) WHERE is_live`; `assignment_guard` trigger; indexes `(version, requirement)`, `(tenant, is_live)`; composite FKs version, requirement, resource, serves. |

### Functions and triggers

| Object | Role |
|---|---|
| `app_tenant_id()` | Reads `current_setting('app.tenant_id', true)` as uuid; null outside a scope, so policies match nothing. |
| `forbid_change()` | Raises on any UPDATE/DELETE: audit events, timetables and versions. |
| `version_guard()` | Legal status transitions, published immutability, `effective_from` on publish. |
| `requirement_guard()`, `requirement_resource_guard()` | Requirements and participants change only while the version is draft or failed. |
| `assignment_guard()` | Inserts only into draft/solving versions and never live; deletes only from draft/solving/failed; on published versions only `is_live` may change. |

### Database roles

`deploy/roles.sql` creates `tt_owner` (migrations, BYPASSRLS), `tt_app` (web), `tt_worker`
(solver worker) and `tt_ops` (read-only, sees every tenant), with login roles `web`, `worker`
and `ops` and per-role statement and lock timeouts. Grants are applied by
`core/migrations/0002_security.py` and extend to future tables through default privileges.

## Background jobs

procrastinate stores its queue in the same PostgreSQL database, so a task is deferred in the
same transaction as the state change that requested it. The worker runs with the `worker`
database role and `--concurrency 2`; each solve is one task. Periodic tasks: `flip_live` daily
after midnight in `TIME_ZONE`, `reset_stale_solving` every few minutes.

## Static files and templates

`collectstatic` runs at image build with whitenoise's compressed manifest storage, so the
container filesystem is read-only at runtime. Pug templates are compiled by pypugjs through the
Django template loader and cached when `DEBUG` is off.
