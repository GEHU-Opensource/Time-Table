# Privacy

## What is held

| Data | Where | Why |
|---|---|---|
| Staff name and email | `core_user` | Login, invitations, attribution of audit events |
| Staff role and department | `core_user` | Authorization |
| Password hash (Argon2), TOTP secret | `core_user`, `otp_totp_totpdevice` | Authentication |
| Teacher codes and optional link to a user | `timetable_resource` | Scheduling; a teacher resource may exist without any account |
| Rooms, sections, batches, subjects, timetables | `timetable_*` | Scheduling |
| Audit events with hashed personal fields | `core_auditevent` | Accountability |
| Sessions | `django_session` | Login state, 8-hour lifetime |
| Login attempts (username, IP) | `axes_*` | Brute-force protection, 15-minute window |
| Request ids, tenant ids | logs | Troubleshooting |

There are no student records. Sections and batches are codes (for example `CSE-3A`), not
rosters. Timetables name teachers by code; the published grid contains no email addresses.

## What is not held

- No student names, enrolment numbers, attendance, marks or contact details.
- No phone numbers or postal addresses of staff.
- No analytics or third-party scripts; the CSP forbids them.
- No request bodies, emails or names in logs or in Caddy access logs (query strings are
  stripped, cookies and authorization headers deleted).

## Audit hashing

`core.audit.scrub` replaces `email`, `name`, `password` and `invite_token_hash` with a 16-hex
SHA-256 digest before an `AuditEvent` is written. An operator can confirm "this event concerns
the user with this email" by hashing the email and comparing, without the log itself being a
directory of staff.

## Retention

| Data | Retention |
|---|---|
| Sessions | expire after 8 hours or browser close; expired rows cleared by `manage.py clearsessions` nightly |
| Login attempts | reset on successful login; stale rows cleared by `manage.py axes_reset` monthly |
| Audit events | kept for the life of the tenant plus 1 year; append-only |
| Users | deactivated (`is_active = false`, `auth_version` bumped) on offboarding; the row stays so audit events keep an actor; name and email are replaced with placeholders on request after 90 days |
| Timetables and versions | never deleted, archived; they are the institution's records |
| Container logs | 5 files of 20 MB per container (`json-file` rotation) |
| Database backups | 30 days (see OPERATIONS.md) |

Deleting a tenant: `archived = true` stops all logins immediately; the data is exported for
the institution and the rows removed by an operator after the agreed period.

## Digital Personal Data Protection Act, 2023 (India)

The DPDP Act received assent in August 2023. The DPDP Rules were notified in November 2025
with a phased commencement; most obligations on data fiduciaries, including notice, consent
management, breach notification and the rights of data principals, apply from May 2027, with
the Data Protection Board and registration provisions earlier. The operating university is the
data fiduciary for its staff data; the hosting operator is a data processor under contract.

How the design meets the Act's requirements as currently understood:

| Obligation | How |
|---|---|
| Purpose limitation and data minimisation (s.4, s.6) | Only name, email, role and department are collected, each needed to run the service. |
| Notice (s.5) | The invite email states what is collected and why; the text is in the tenant's settings so each university can adapt it. |
| Security safeguards (s.8(5)) | See SECURITY.md: encryption in transit, Argon2, RLS, least-privilege roles, audit. |
| Breach notification (s.8(6)) | Operators notify the tenant administrator and the Board within the period set by the Rules; the audit log and request ids support the investigation. |
| Erasure when purpose is served (s.8(7)) | Offboarding deactivates and later pseudonymises the user; sessions and login attempts expire on their own. |
| Rights of access and correction (s.11, s.12) | Users see and edit their name on the account page; administrators export a user's data from the users panel. |
| Grievance redressal (s.13) | Tenant settings hold a grievance officer contact shown on the login page. |
| Children's data (s.9) | Not applicable: no student data. |
| Cross-border transfer (s.16) | Deploy in India; `BASE_DOMAIN` and the database stay in one region. |

Review this section when the remaining Rules commence (May 2027) and whenever the Board
publishes guidance.

## Contacts

The tenant administrator is the first point of contact for staff; operators are reached at
`privacy@<BASE_DOMAIN>`.
