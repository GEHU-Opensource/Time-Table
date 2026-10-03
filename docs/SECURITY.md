# Security model

The system assumes that any single layer can fail: a template can forget to escape, a view
can forget a permission, a query can forget a filter. Each layer below is independent and
covers the one above it.

## 1. Settings (`config/settings.py`)

- `ENV` must be `dev`, `test` or `prod`; `DEBUG` can only be true in `dev`.
- `SECURE` (default true in prod) turns on HTTPS redirect, HSTS (1 year, subdomains,
  preload), `__Host-` session cookie, `X-Forwarded-Proto` trust and whitenoise manifest
  storage.
- Sessions in the database, 8-hour lifetime, renewed every request, expire on browser close,
  `HttpOnly`, `SameSite=Lax`. CSRF tokens live in the session (`CSRF_USE_SESSIONS`).
- `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `COOP: same-origin`,
  `X-Content-Type-Options: nosniff`.
- Uploads capped at 5 MB in memory only (`MemoryFileUploadHandler`), 2000 form fields.
- `core/checks.py` adds deploy checks: DEBUG in prod, SECURE off in prod, SECRET_KEY under
  50 characters. `manage.py check --deploy --fail-level WARNING` runs in CI and at every web
  container start.

## 2. Database roles (`deploy/roles.sql`, `core/migrations/0002_security.py`)

| Role | Used by | Rights |
|---|---|---|
| `tt_owner` | migrations only | owns the schema, `BYPASSRLS` |
| `tt_app` (login `web`) | gunicorn | `SELECT, INSERT, UPDATE, DELETE` on tables, no `DELETE` on timetables, versions, resources, subjects; no `UPDATE/DELETE` on audit; 5 s statement and 2 s lock timeouts |
| `tt_worker` (login `worker`) | procrastinate worker | as `tt_app`, 120 s statement timeout |
| `tt_ops` (login `ops`) | operators | `SELECT` on everything across tenants, 600 s timeout |

Passwords are substituted into `roles.sql` at first database start by `deploy/init-db.sh`
from `OWNER_DB_PASSWORD`, `WEB_DB_PASSWORD`, `WORKER_DB_PASSWORD`, `OPS_DB_PASSWORD`.

## 3. Row-level security

Every tenant table has `ENABLE` and `FORCE ROW LEVEL SECURITY` with policy
`tenant_id = app_tenant_id()` for reads and writes and a read-only `ops_read` policy for
`tt_ops`. `app_tenant_id()` reads a transaction-local GUC that `TenantMiddleware` sets inside
`tenant_scope`. Outside a scope the GUC is empty, the function returns null and no row
matches. `otp_totp_totpdevice` is covered by a policy through `core_user`. Composite foreign
keys prevent cross-tenant references even for a role that bypasses RLS.

## 4. Authentication

- Passwords hashed with Argon2 (`argon2-cffi`), minimum 12 characters plus Django's
  similarity, common-password and numeric validators.
- `django-axes`: 5 failures per (username, IP) lock the pair for 15 minutes; reset on success.
  Behind the proxy, one trusted forwarder is configured.
- `core.auth.TenantBackend` only authenticates users of the request's tenant.
- `auth_version` on the user is part of the session hash, so bumping it (password reset,
  role change, offboarding) invalidates every session at once.
- MFA: TOTP via `django-otp`. Any user whose role holds a privileged permission
  (`timetable.publish`, `user.manage`, `role.manage`, `tenant.settings`) must enrol and verify
  before `PermissionedView` lets a request through (`core.perms.mfa_redirect`).

## 5. Invites

New users are created without a usable password. An invite token is generated with
`secrets.token_urlsafe`, only its SHA-256 (`invite_token_hash`) is stored, and the lookup is a
database-side equality on the hash, which is constant time with respect to the token. Invites
expire after `INVITE_TTL` (72 h) and are single use. The invite email contains the link; the
log and audit trail contain only the hash prefix.

## 6. Authorization

Permissions are string codes (`core.perms.Perm`) held by roles; a role's permission array is
check-constrained to known codes. Every page and panel view subclasses `PermissionedView` with
an explicit permission; a view without one raises `ImproperlyConfigured` at request time, so
"forgot to protect" fails closed. Object-level access uses `can(user, perm, obj, write)`:
department-scoped users may write only their department's objects and read tenant-wide ones.
Querysets expose `visible_to(user)` and `owned_by(user)`, and objects outside the user's scope
return 404 rather than 403, so their existence is not disclosed. Templates gate buttons with
`if 'perm.code' in perms`, which is a convenience; the view check is the control.

## 7. Audit

`core.audit.audit(actor, action, obj, before, after)` writes an `AuditEvent` with the request
id. Fields named `email`, `name`, `password` and `invite_token_hash` are replaced by a 16-hex
SHA-256 prefix, so the audit log never contains personal data in clear. The table is
append-only (revoked `UPDATE/DELETE`, `forbid_change` trigger).

## 8. Content Security Policy and htmx

`django-csp` sends `default-src 'self'; script-src 'self' 'nonce-...'; style-src 'self';
img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action
'self'`. htmx is vendored and loaded from `static/`, configured with `selfRequestsOnly`,
`allowEval: false`, `allowScriptTags: false`, no indicator styles and no history cache.
Templates may not contain `<script`, `<style`, `style=`, `hx-on`, `js:`, `!=`, `!{` or
`|safe` (`scripts/check_templates.py`), so there is no path to inline code or raw HTML.

## 9. Uploads and exports

Imports accept `.xlsx` parsed by `openpyxl` with `defusedxml` active, read fully in memory and
capped at 5 MB by Django and 6 MB by Caddy. Rows are validated against the tenant's resources
before any write; a failed import writes nothing. Exports are generated server side and served
with `Content-Disposition: attachment`; cell values that start with `=`, `+`, `-` or `@` are
prefixed to prevent formula injection.

## 10. Solver sandbox and rate limit

Solves run in the worker as a subprocess with `RLIMIT_AS = SOLVER_MEMORY_BYTES` (2 GiB), a
wall-clock limit (`SOLVER_MAX_SECONDS`, 600 s) and `SOLVER_MAX_MODEL_SIZE` literals, with a
fixed worker count. A tenant may start `SOLVES_PER_TENANT_PER_HOUR` (10) solves. Versions
stuck in `solving` beyond `STALE_SOLVE_GRACE` are reset to `failed`. The worker container has a
3 GiB memory limit, a read-only root filesystem and no capabilities.

## 11. Logging

`core/logging.py` emits one JSON object per line with time, level, logger, message,
`request_id` and `tenant_id`, never request bodies, emails or names. Caddy access logs are
JSON with the query string removed from the URI and `Cookie`, `Authorization` and `Set-Cookie`
headers deleted. gunicorn access logs go to stdout. Nothing is written to the container
filesystem.

## 12. Transport and edge

Caddy obtains wildcard certificates through the DNS-01 challenge (no port 80 validation,
no per-tenant certificate issuance), redirects HTTP to HTTPS, removes the `Server` header,
limits bodies to 6 MB and forwards `X-Request-ID`. Only Caddy publishes ports; PostgreSQL is
on an internal network with no external route.

## 13. Containers

The application image runs as uid 10001, has no shell for that user, is read-only at runtime
with a 64 MB `/tmp` tmpfs, drops all capabilities, sets `no-new-privileges`, and has memory
and pid limits. Static files are collected at build time.

## 14. Supply chain

- Every GitHub Action is pinned to a commit SHA (`actions/checkout` v6.1.0,
  `actions/setup-python` v6.1.0, `gitleaks/gitleaks-action` v2.3.9 at
  `ff98106e4c7b2bc287b24eaf42907196329070c7`).
- CI runs `pip-audit -r requirements.txt` and gitleaks over the full history.
- Workflow permissions are `contents: read`.
- Dependencies are pinned to compatible ranges in `requirements.txt`.

## Follow-ups

| Item | Why it matters | Plan |
|---|---|---|
| Hashed lock file | Ranges allow a compromised release to install. | `uv pip compile --generate-hashes` to `requirements.lock`; `pip install --require-hashes -r requirements.lock` in Dockerfile and CI. |
| SSO (SAML/OIDC) | Universities want institutional login and offboarding. | Add an OIDC backend behind `TenantBackend`, per-tenant issuer in `Tenant.settings`. |
| Backups with restore drills | A backup that was never restored is a hope. | Nightly `pg_dump` to object storage with 30-day retention; quarterly restore into a staging stack, documented in OPERATIONS.md. |
| Two-approver MFA reset | A single admin resetting another admin's MFA is the social-engineering path. | Reset requests recorded as audit events and require a second `user.manage` holder to confirm within 24 h. |
| procrastinate table privileges | The worker role currently holds full DML on every table through default privileges. | Restrict `tt_worker` to `timetable_assignment`, `timetable_version` and the `procrastinate_*` tables; revoke `core_user` writes. |
| `tt_ops` usage | Operators reading across tenants is powerful. | Route `ops` logins through a bastion with session recording; rotate the password per incident; log `pg_stat_activity` for the role. |
| Content-Security-Policy reporting | Silent CSP failures hide attempted injection. | Add `report-to` with a small endpoint and alerting. |
| Dependabot or Renovate | Range pins still need a human to bump. | Enable weekly PRs for `requirements*.txt` and the Actions SHAs. |

## Reporting

Security issues go to the operators' address configured in `DEFAULT_FROM_EMAIL`'s domain
(`security@<BASE_DOMAIN>`). Do not open public issues for vulnerabilities.
