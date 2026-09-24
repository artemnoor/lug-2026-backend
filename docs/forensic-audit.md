# LUG 2026 — forensic audit of the reference backend

Дата фиксации baseline: 24 сентября 2026 года.

Reference repository: [`artemnoor/lug-2026`](https://github.com/artemnoor/lug-2026).
Он был клонирован отдельно во время аудита и не является частью этого runtime.

## Evidence baseline

| Проверка | Результат | Интерпретация |
| --- | --- | --- |
| `python -m pytest -q` | `49 passed, 6 skipped` | Unit/regression suite проходит; шесть integration cases требуют внешние PostgreSQL/S3 endpoints. |
| `ruff check apps/api/app tests` | pass | Python baseline lint проходит. |
| `npm run check:openapi` | `openapi: 47 operations covered` | 47 уникальных non-HEAD операций; контракт также содержит HEAD для private upload, всего 48 method operations. |
| `npm run check` | quality pass, затем `eslint is not recognized` | Полный JS check не воспроизводится без установки reference `node_modules`; это tooling blocker baseline. |

## Runtime entrypoints and composition

- Node gateway: `server.js` and `apps/web/src/server.js`; it provides same-origin
  static assets, CSRF bootstrap, proxying of `/api/*`, `/uploads/*`, `/readyz`,
  and `/metrics`.
- FastAPI: `apps/api/app/main.py`; its lifespan builds `AppConfig`, persistence,
  file storage, email, rate limiter, `AppContext`, repositories, and services.
- Router groups are split into `routes/auth.py`, `password_reset.py`,
  `registration.py`, `user.py`, `user_profile.py`, `user_notifications.py`,
  `admin.py`, `admin_settings.py`, and `operations.py`.
- The HTTP boundary manually parses JSON and returns dictionaries. Built-in
  FastAPI docs are disabled and `/api/openapi.json` serves a checked-in contract.
- The application has one context object and one broad persistence adapter that is
  cast to many repository protocols. This is a useful seam for the rewrite but not
  an acceptable target dependency shape.

## Actual capability map

### Auth and identity

- Email/password login with `lug_session` cookie and Argon2id/scrypt support.
- Session listing, other-session revocation, logout, generic credential errors.
- Email verification with six-digit HMAC, TTL, cooldown, attempt limit, and email
  delivery; registration creates a session only after verification.
- Password reset with separate HMAC state and session revocation.
- CSRF double-submit cookie/header on all mutations.

### Teams and participant cabinet

- Team registration, invite-based join, capacity and registration-window checks.
- Team profile, invite rotation, captain-only mutations, member identity review.
- Profile fields, phone/messenger normalization, student-card replacement.
- Dashboard projection containing user/team/members/achievements/notifications/
  settings/quota/admission fields used by the frontend.

### Materials and review

- Local stream uploads and S3 multipart intent/complete flows.
- Student cards, attachments, video uploads, quotas, content sniffing, optional
  scanner and private owner/team/admin access.
- Achievement creation/deletion with portfolio window and pending review.
- Team video URL/file submission with provider and criteria validation.
- Admin overview, collections, audit log, quota, identity/team/achievement/video
  review, settings, and broadcast notifications.
- Public config/results and email copies of notifications.
- Chat API/fields are intentionally absent and old chat notifications are rejected.

## Reference domain/dependency findings

### CRITICAL

None reproduced as an immediate baseline exploit in the tested development flow.
Production still depends on external TLS, secret management, private object
storage/scanner/SMTP endpoints, and backups; local Compose now supplies concrete
development implementations for those integration seams.

### HIGH

1. File access policy is expressed in repository ownership checks but the storage
   lifecycle does not make the `clean` scan state a universal read prerequisite;
   the new media module must fail closed for pending/rejected uploads.
2. `apps/api/app/infrastructure/s3_storage.py` performs synchronous Redis intent
   operations from async methods; the new adapter must use `redis.asyncio` and
   bounded timeouts.
3. `apps/api/app/infrastructure/local_storage.py` writes files and invokes scanner
   processes from async workflows; the new adapter must move blocking work off the
   event loop.
4. The checked-in OpenAPI exposes generic `object` schemas and route responses are
   mostly untyped dictionaries, making client and security review contracts weak.

### MEDIUM

1. `main.py` and `context.py` read environment variables outside the typed config
   boundary (`LUG_ALLOWED_HOSTS`, tracing/bootstrap values).
2. `shared/domain.py` combines timing, validation, projections, quotas,
   notifications, and review helpers; it is cohesive only at the competition-rule
   level and is too broad for a change-isolated target module.
3. `json_store_commands.py`, `postgres_writes.py`, `postgres_queries.py`,
   `postgres_registration.py`, and `s3_storage.py` exceed the reference quality
   warning threshold and hide multiple business seams in large adapters.
4. Postgres tables retain a broad `payload JSONB` fallback alongside canonical
   columns; transaction boundaries are hidden in methods named `*_atomic` rather
   than owned by use cases.
5. Routers duplicate cookie/session lookup, JSON validation helpers, rate checks,
   and auth policy branching.
6. Infrastructure imports `http.errors.ApiError` in file-storage code, coupling
   persistence/storage to HTTP.
7. Profile replacement uses compensating storage deletion and previously swallowed
   delete errors; the new code must warn with context and keep the domain result
   deterministic.

### LOW

1. Legacy configuration exposes many flat aliases in addition to nested settings.
2. Development JSON persistence and process-local rate limiting are intentionally
   single-instance conveniences but easy to mistake for production options.
3. The reference gateway/API documentation is split between generated-like JSON,
   README, and frontend assumptions rather than one generated source of truth.

## Security and authorization matrix

| Actor | Allowed | Must be rejected |
| --- | --- | --- |
| Anonymous | public config/results/invite lookup, login, registration uploads/flows, password-reset request | dashboard, private uploads, sessions, participant/admin mutations |
| Authenticated participant | own dashboard/profile/uploads/achievements/notifications; own team read | admin collections/reviews, another user's upload, team mutations without captain role |
| Team captain | participant capabilities plus team profile/invite/video and team-owned flows | admin endpoints and unrelated team objects |
| Reviewer/admin | admin overview/collections/audit/reviews/settings/broadcast; permitted private file access | unvalidated/mass-assigned role or arbitrary object access outside policy |
| Operations caller | readiness/metrics direct access only with operations token or loopback policy | unauthenticated external readiness/metrics in hardened deployment |

## Database and external integrations

- Alembic revisions `0001` through `0012` create settings, users, teams,
  achievements, notifications, sessions, uploads, verification/reset state,
  audit log, and encrypted email outbox. The runtime uses asyncpg SQL rather than
  SQLAlchemy ORM; the rebuild changes this to SQLAlchemy 2.x models and ports.
- PostgreSQL is the shared production source of truth. Redis supplies shared rate
  limiting and multipart intent state. Local disk is development-only; the
  rebuilt Compose environment uses MinIO, while production uses private
  S3-compatible storage, server-side encryption, signed URLs, and AV.
- Email modes are local log and SMTP; local Compose runs Mailpit and production
  requires a managed SMTP endpoint and encrypted durable outbox state.

## Target boundary decision

The behavior supports these bounded modules:

```text
auth       users       teams
   \          |          /
       media  portfolio  video
             |
       notifications  content
             |
      admin interface facade
```

`admin` is an application/interface layer. It calls domain application operations
owned by teams/users/portfolio/video/notifications/content; it does not create
parallel admin repositories or duplicate review rules. `media` is separate because
file lifecycle, scanning, storage, and ownership are cross-cutting infrastructure
with independent security risk.

## Unknowns and assumptions

- The reference contract checker reports 47 operations because it counts unique
  non-HEAD operations; `GET/HEAD /uploads/{filename}` is one path with two HTTP
  methods. The new matrix records both methods and preserves both.
- The new backend is built without moving the reference frontend. Compatibility is
  proven against the extracted consumer calls and API smoke scenarios, not by
  bundling the web app.
- A fresh PostgreSQL database is the migration target. A legacy JSON importer is
  provided as an explicit operation; importing is never automatic at process
  startup.
