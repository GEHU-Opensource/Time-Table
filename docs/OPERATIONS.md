# Operations

All commands run on the host from the repository root unless noted. Docker Compose v2 is
required (`docker compose`, not `docker-compose`).

## Layout

```
deploy/Dockerfile          application image (web, worker, migrate)
deploy/Dockerfile.caddy    Caddy built with the DNS provider plugin
deploy/compose.yaml        the stack
deploy/Caddyfile           edge configuration
deploy/entrypoint.sh       waits for PostgreSQL, runs checks or migrations
deploy/init-db.sh          first-start role creation from roles.sql
deploy/roles.sql           database roles and timeouts
```

Services: `postgres` (internal network only), `migrate` (one-shot, owner role), `web`
(gunicorn, `web` role), `worker` (procrastinate, `worker` role), `caddy` (the only service
with published ports: 80, 443, 443/udp).

## First deploy

1. DNS: an `A`/`AAAA` record for `BASE_DOMAIN` and a wildcard `*.BASE_DOMAIN` to the host.
   Create an API token for the DNS provider with permission to edit TXT records of the zone.
2. Create `.env` in the repository root (never committed):

   ```
   ENV=prod
   SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(64))">
   BASE_DOMAIN=timetable.example.edu
   EMAIL_URL=smtp+tls://user:password@smtp.example.edu:587
   DEFAULT_FROM_EMAIL=timetable@example.edu
   TIME_ZONE=Asia/Kolkata
   POSTGRES_PASSWORD=<openssl rand -hex 32>
   OWNER_DB_PASSWORD=<openssl rand -hex 32>
   WEB_DB_PASSWORD=<openssl rand -hex 32>
   WORKER_DB_PASSWORD=<openssl rand -hex 32>
   OPS_DB_PASSWORD=<openssl rand -hex 32>
   ACME_EMAIL=ops@example.edu
   CADDY_DNS_PLUGIN=cloudflare
   CADDY_DNS_PROVIDER=cloudflare
   CADDY_DNS_TOKEN=<provider API token>
   DB_SSLMODE=disable
   ```

   Database passwords must be `[A-Za-z0-9_-]` only; `init-db.sh` refuses others because it
   substitutes them into `roles.sql` with `sed`. `DB_SSLMODE=disable` is correct for the
   bundled PostgreSQL on the internal Docker network; use `verify-full` with a managed
   database and mount its CA.

3. Build and start:

   ```sh
   docker compose --env-file .env -f deploy/compose.yaml build
   docker compose --env-file .env -f deploy/compose.yaml up -d
   docker compose --env-file .env -f deploy/compose.yaml logs -f migrate web caddy
   ```

   `migrate` exits 0 after applying migrations; `web` and `worker` wait for it. The first
   certificate takes about a minute (DNS propagation of the challenge record).

4. Verify: `curl -sS https://healthz.$BASE_DOMAIN/healthz/` returns 200 and
   `https://$BASE_DOMAIN/` returns 404 with the landing text.

## Creating a tenant and its first administrator

```sh
docker compose --env-file .env -f deploy/compose.yaml run --rm --entrypoint "" web \
  python manage.py create_tenant --name "Graphic Era Hill University" --slug gehu
docker compose --env-file .env -f deploy/compose.yaml run --rm --entrypoint "" web \
  python manage.py seed_tenant_admin --tenant gehu --email admin@gehu.ac.in --name "Admin"
```

`seed_tenant_admin` creates the `Admin`, `HOD` and `Faculty` roles from `ROLE_PRESETS`,
creates the user with an unusable password and prints a one-time set-password link valid for
72 hours. Send it over a channel you trust; it is not emailed. The administrator must enrol
TOTP on first login because `Admin` holds privileged permissions.

Both commands use `Model.all_objects` under the hood and must run with the `web` role or
`tt_owner`; they are the only place `all_objects` is permitted.

## Running the worker

The `worker` service runs `python manage.py procrastinate worker --concurrency 2`. Two
concurrent solves fit the 3 GiB memory limit with the 2 GiB per-solve `RLIMIT_AS`. Scale with
`docker compose up -d --scale worker=2` if solves queue up; each replica needs 3 GiB.

Periodic tasks (`flip_live`, `reset_stale_solving`, `clearsessions`) are registered as
procrastinate periodic tasks and run inside the worker; no cron is needed.

## Rotating `SECRET_KEY`

1. Set `SECRET_KEY_FALLBACKS=<old key>` and `SECRET_KEY=<new key>` in `.env`.
2. `docker compose --env-file .env -f deploy/compose.yaml up -d web worker` (sessions signed
   with the old key keep working for the 8-hour session lifetime).
3. After 24 hours remove `SECRET_KEY_FALLBACKS` and restart again.

Rotating database passwords: `ALTER ROLE web PASSWORD '...'` as `postgres`, update `.env`,
restart the affected service. `init-db.sh` runs only on an empty data volume and will not
overwrite existing roles.

## Backups

Nightly logical dump with the owner role from a host cron job:

```sh
docker compose --env-file .env -f deploy/compose.yaml exec -T postgres \
  pg_dump -U postgres -d timetable --format=custom --no-owner --no-acl \
  > /backups/timetable-$(date +%F).dump
```

Encrypt and copy the file off the host (for example `age` plus object storage). Keep 30 daily
dumps. Also back up the `caddy-data` volume if you want to avoid re-issuing certificates on a
rebuild; it is not essential.

Procrastinate's queue is in the same database and is included; in-flight solves at dump time
are simply retried after a restore.

## Restoring

Restore into a fresh stack, then switch DNS, rather than restoring over a live database.

```sh
docker compose --env-file .env -f deploy/compose.yaml up -d postgres
docker compose --env-file .env -f deploy/compose.yaml exec -T postgres \
  pg_restore -U postgres -d timetable --clean --if-exists --no-owner --no-acl \
  < /backups/timetable-YYYY-MM-DD.dump
docker compose --env-file .env -f deploy/compose.yaml exec -T postgres \
  psql -U postgres -d timetable -c "REASSIGN OWNED BY postgres TO tt_owner"
docker compose --env-file .env -f deploy/compose.yaml up -d
```

Roles come from `init-db.sh` on the fresh volume, and RLS policies and triggers are part of
the dump. Run a restore drill every quarter and record the time it took.

## Upgrading

```sh
git pull
docker compose --env-file .env -f deploy/compose.yaml build
docker compose --env-file .env -f deploy/compose.yaml up -d
```

`migrate` runs again before `web` and `worker` restart. Migrations are written to be
backwards compatible with the previous release so a rolling restart does not fail requests.

## Reading logs

All services log JSON to stdout.

```sh
docker compose --env-file .env -f deploy/compose.yaml logs -f --since 1h web worker caddy
```

Application lines carry `request_id` and `tenant_id`. Caddy generates the id and forwards it as
`X-Request-ID` but does not include it in its own access log, so correlate Caddy lines with
application lines by timestamp, path and remote address. To follow one request:

```sh
docker compose -f deploy/compose.yaml logs web | grep '"request_id": "<uuid>"'
```

Audit events are in the database: as the `ops` role,
`SELECT created_at, action, object_type, object_id, request_id FROM core_auditevent ORDER BY
created_at DESC LIMIT 50;`. The `ops` role sees every tenant and cannot write.

## Health and alerts

- Docker's `HEALTHCHECK` calls `/healthz/` inside the web container every 30 s.
- Monitor `https://healthz.$BASE_DOMAIN/healthz/` from outside.
- Alert on `level: ERROR` lines, on `migrate` exiting non-zero, and on versions in `solving`
  older than `STALE_SOLVE_GRACE` (`SELECT count(*) FROM timetable_version WHERE status =
  'solving' AND created_at < now() - interval '15 minutes'` as `ops`).

## Local development without Docker

See README.md. `createdb timetable_dev`, `manage.py migrate` as your own superuser role, and
`manage.py runserver`; the tenant is reached at `http://<slug>.localhost:8000/`.
