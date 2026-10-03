# Decisions

Each entry: the decision, why, and what it costs.

## CP-SAT instead of the genetic algorithm

The earlier prototype used a genetic algorithm. It produced timetables with clashes it could
not explain, took minutes to converge on medium inputs, and offered no way to prove
infeasibility. OR-Tools CP-SAT models every hard rule as a constraint, so a returned solution
cannot violate them; it reports `INFEASIBLE` with reasons we can map back to requirements; it
is deterministic for a fixed seed; and soft preferences become objective terms. The cost is a
native dependency (a 30 MB wheel) and memory that grows with model size, which is why solves
run in a sandboxed subprocess with a model-size cap.

## One repository, one deployable

Web, worker and solver share one codebase and one image. Contracts between them are Python
dataclasses (`solver/types.py`), checked by `import-linter` so the solver stays free of
Django. Separate repositories would add versioning ceremony for a team of this size.

## Pug through pypugjs, plain Django templates as the fallback

Pug's indentation syntax keeps templates short and makes unbalanced markup impossible.
pypugjs compiles Pug to Django template language, so every Django tag, filter and the
auto-escaping model still apply. If pypugjs ever blocks an upgrade, the compiled output can be
committed as `.html` templates and the loader removed with no change to views. Forbidden
constructs (`!=`, `!{`, `|safe`, inline scripts and styles) are rejected by
`scripts/check_templates.py` so the templates never bypass escaping or the CSP.

## Twelve tables

The schema is the smallest that keeps every entity a university will ask about as a row:
tenant, department, role, user, audit event, resource, subject, timetable, version,
requirement, requirement participant, assignment. Teachers, rooms, sections and batches share
`resource` because the solver treats them uniformly as things that cannot be in two places at
once; a `kind` column with check constraints keeps the kind-specific invariants. Splitting
them into four tables would quadruple the composite foreign keys and policies for no gain.

## Occupancy rows

An `Assignment` is one row per resource per period rather than one row per session. That
makes the no-double-booking rule a unique index instead of application logic, lets a batch row
record which section it `serves`, and makes "who is in room X at 10:00" a primary-key lookup.
The cost is more rows (a 3-period lab with a teacher, a room and a batch is nine rows), which
PostgreSQL handles comfortably at university scale.

## `is_live` partial unique index

Publishing a version must not be allowed to collide with another live timetable in the same
tenant even if the validator were wrong. `UNIQUE (tenant, resource, day, period) WHERE
is_live` is the last line: the `flip_live` transaction either commits a consistent set of live
rows or fails. Draft versions do not carry `is_live`, so experimenting never conflicts.

## RLS with FORCE and composite foreign keys

The ORM filters by tenant through `TenantManager`, but a single missed `all_objects` or a raw
query would leak. Row-level security with `FORCE ROW LEVEL SECURITY` applies to the table owner
as well, and the application roles cannot bypass it; the tenant id arrives through a
transaction-local GUC set by the middleware. Composite foreign keys `(tenant_id, fk) ->
(tenant_id, id)` make it impossible to reference a row of another tenant even with RLS
disabled for an administrator. The cost is a `UNIQUE (tenant_id, id)` index per table and a
`DEFERRABLE` constraint set.

## procrastinate instead of Celery

The queue lives in PostgreSQL. A job is deferred in the same transaction that changes a
version's status, so there is never a job for a state that was rolled back, nor a state waiting
for a job that was lost. No Redis or RabbitMQ to run, back up or secure. The cost is lower
throughput than a dedicated broker, irrelevant for tens of solves per hour.

## No platform administrator in the web application

There is no cross-tenant user interface. Tenants are created and their first administrator
seeded with management commands run by an operator with shell access; investigations use the
read-only `tt_ops` database role. A platform login would be a single credential whose
compromise exposes every university, and would need its own MFA, audit and RLS bypass paths.

## No comments

Code contains no comments or docstrings. A `#` line other than a shebang fails CI
(`scripts/check_no_comments.py`, also run by `tests/test_no_comments.py`). The intent is that
names carry meaning, tests show behaviour and `docs/` holds the reasoning. Comments drift from
code silently; tests and names fail loudly. The cost is that a reader must open the docs for
the "why", which is why every doc file links to the module it explains.

## Hashed lock file as a follow-up

`requirements.txt` pins ranges, so `pip install --require-hashes` is not possible yet. The
next step is `uv pip compile --generate-hashes requirements.txt -o requirements.lock` and
installing from that lock in `deploy/Dockerfile` and CI. Until then `pip-audit` in CI flags
known-vulnerable resolutions.
