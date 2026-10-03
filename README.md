# Time-Table

Multi-tenant university timetable system: Django 5.2, Pug templates, htmx, PostgreSQL and the
OR-Tools CP-SAT solver. Each university is a tenant on its own subdomain; every tenant table is
protected by PostgreSQL row-level security. A clash cannot leave the solver, cannot be written
to the database, and is re-checked by an independent validator before anything is published.

## Run locally

Requires Python 3.13 and PostgreSQL 14 or newer.

```sh
createdb timetable_dev
cp .env.example .env
python3.13 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py create_tenant --name "GEHU" --slug gehu
.venv/bin/python manage.py seed_tenant_admin --tenant gehu --email admin@example.com --name "Admin"
.venv/bin/python manage.py runserver
```

Open http://gehu.localhost:8000/ and use the set-password link printed by `seed_tenant_admin`.
Run the background worker with `.venv/bin/python manage.py procrastinate worker`.

## Tests

```sh
.venv/bin/pytest
```

pytest-django creates a test database on the local PostgreSQL; set `TEST_DB_NAME` to run
several suites side by side. The suite includes `tests/test_no_comments.py`, which runs the
repository lint scripts, so `pytest` alone enforces the rules below. The full CI sequence is in
`.github/workflows/ci.yml`:

```sh
.venv/bin/ruff format --check . && .venv/bin/ruff check .
.venv/bin/python scripts/check_no_comments.py
.venv/bin/python scripts/check_templates.py
.venv/bin/lint-imports
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/pytest -q
```

## Deploy

`deploy/compose.yaml` runs PostgreSQL 16, a one-shot migration job, gunicorn, the
procrastinate worker and Caddy with wildcard TLS via DNS-01. Only Caddy publishes ports.
Step-by-step instructions, tenant creation, key rotation, backups and restores are in
[docs/OPERATIONS.md](docs/OPERATIONS.md).

## Repository layout

```
config/      settings from the environment, URL root, WSGI
core/        tenancy, users, roles, permissions, audit, auth, health, management commands
timetable/   resources, subjects, timetables, versions, requirements, assignments, services
solver/      pure-Python CP-SAT model, validator and dataclass contracts (no Django)
templates/   Pug templates (layout, admin shell, panels, errors)
static/      stylesheet and vendored htmx
deploy/      Dockerfiles, Compose stack, Caddyfile, entrypoint, database roles
scripts/     repository lint scripts run by CI and pytest
tests/       pytest suite
docs/        architecture, constraint table, decisions, security, privacy, operations
```

## Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, request flow, solve and publish flows, versioning, the data model table by table |
| [docs/CONSTRAINTS.md](docs/CONSTRAINTS.md) | Every scheduling rule, hard or soft, and where each is enforced |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Why CP-SAT, one repo, Pug, twelve tables, occupancy rows, RLS, procrastinate, no platform admin, no comments |
| [docs/SECURITY.md](docs/SECURITY.md) | The layered security model and its follow-ups |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Data held, retention, DPDP Act 2023 notes |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | First deploy, tenants, rotation, backups, restores, worker, logs |

## The no-comments rule

Code in this repository contains no comments and no docstrings: Python, Pug, SQL, shell,
YAML, Dockerfiles and the Caddyfile. A `#` line other than a shebang (or a `noqa` pragma)
fails CI through `scripts/check_no_comments.py`. Explanations live in three places instead:
names (a function is called what it does), tests (`tests/` shows the behaviour), and `docs/`
(the reasoning). Generated migrations are excluded from the check. Templates are additionally
checked by `scripts/check_templates.py`, which forbids inline scripts and styles, `hx-on`,
`js:` and every unescaped-output construct.
