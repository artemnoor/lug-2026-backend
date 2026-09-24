# LUG 2026 backend rebuild progress

## Current phase

Phase 8 verification and final architecture audit are complete; this follow-up
also closed the local dependency integration gap. The detailed ultra plan was
maintained in the parent workspace; this repository contains the implementation
evidence and final audit below.

## Completed evidence

- Reference [`artemnoor/lug-2026`](https://github.com/artemnoor/lug-2026) was
  cloned read-only during the forensic audit.
- Reference API entrypoint, route modules, application services, persistence,
  migrations, storage, email, rate limiting, security, tests, Docker, docs, and
  frontend API consumers inspected.
- Baseline `pytest`: 49 passed, 6 skipped.
- Baseline Ruff: pass.
- Baseline OpenAPI check: 47 unique non-HEAD operations; 48 HTTP method entries
  including HEAD.
- Baseline full JS check: blocked by missing reference `eslint` executable after
  Python/quality checks completed.
- Frontend consumer contract extracted from `apps/web/public/js/store.js`,
  `auth.js`, `cabinet.js`, and smoke flows.

## Target decisions

- New code is a modular monolith, not a copy of `apps/api/app`.
- Business modules: auth, users, teams, media, portfolio, video, notifications,
  content; admin is an interface façade.
- PostgreSQL + SQLAlchemy 2.x + Alembic is the deployment persistence path.
- SQLite is a deterministic local/test adapter only; no JSON store in the new
  runtime.
- Module contracts are public `contracts.py`/ports; internal implementation
  imports are prohibited by tests.
- Application operations own transaction boundaries through a Unit of Work;
  repositories do not commit.
- Internal structured errors serialize to the legacy `{error, code, details?}`
  wire shape for current frontend compatibility.
- Built-in generated `/docs`, `/redoc`, `/openapi.json` are enabled; old
  `/api/openapi.json`, `/healthz`, `/readyz`, and `/livez` remain aliases.
- Chat remains intentionally absent.
- Admin review writes delegate to teams/users/portfolio/video application
  operations; admin persistence is read-oriented.
- The initial Alembic migration uses explicit operations and supports offline SQL;
  no startup DDL is required.

## Findings to fix rather than copy

- Weak generic response schemas and checked-in OpenAPI.
- Raw environment reads outside typed settings.
- One broad adapter satisfying all repository ports.
- JSONB payload fallback for core PostgreSQL fields.
- Hidden transaction boundaries and duplicated session/policy logic.
- Blocking local file/scanner work and synchronous Redis calls in async storage.
- Upload lifecycle must gate private reads on a clean scan.
- Infrastructure must not raise HTTP exceptions.

## Implementation log

| Date | Change | Evidence |
| --- | --- | --- |
| 2026-09-24 | Reference audited and ultra plan completed | reference repository and parent workspace plan |
| 2026-09-24 | Foundation, typed settings, UoW, errors, security, HTTP policy, health/readiness and observability implemented | `app/core/`, `app/main.py`, smoke tests |
| 2026-09-24 | Domain modules and SQLAlchemy adapters rebuilt with explicit module contracts | `app/modules/`, architecture boundary tests |
| 2026-09-24 | Explicit relational Alembic schema replaced metadata-driven migration | `alembic/versions/0001_initial_schema.py`, migration regression test |
| 2026-09-24 | Admin façade, generated OpenAPI and compatibility aliases completed | `app/modules/admin/`, OpenAPI smoke test |
| 2026-09-24 | Docker, Compose, CI, legacy JSON importer, README/architecture/ADR docs added | `Dockerfile`, `docker-compose.yml`, `scripts/import_legacy_json.py`, `docs/` |
| 2026-09-24 | Security/authorization regression coverage added | `tests/test_security_and_capabilities.py` |
| 2026-09-24 | Final audit fixed PostgreSQL TLS propagation, enforced JSON body limits, completed S3 scan/size gates, and corrected generated OpenAPI error/security metadata | `app/core/database.py`, `app/core/http.py`, `app/infrastructure/storage.py`, `app/main.py` |
| 2026-09-24 | Legacy importer regression fixture and package discovery added | `tests/test_legacy_import.py`, `pyproject.toml` |
| 2026-09-24 | Replaced S3/scanner/SMTP configuration-only local setup with concrete MinIO, ClamAV and Mailpit Compose services; added network scanner adapter and dependency readiness checks | `docker-compose.yml`, `app/infrastructure/scanner.py`, `app/infrastructure/storage.py`, `app/infrastructure/email.py`, `tests/test_local_dependencies.py` |

## Verification evidence

- `pytest -q`: 13 passed, 1 upstream Starlette/httpx deprecation warning.
- `ruff format --check app tests alembic scripts`: pass.
- `ruff check app tests alembic scripts`: pass.
- `mypy app`: pass (91 source files).
- Clean SQLite and PostgreSQL migrations: upgrade → downgrade → upgrade and
  `alembic check` passed; offline SQL generation passed.
- Generated OpenAPI: 49 paths, 49 operations, three security schemes; every
  operation documents the shared error responses, and private uploads declare
  session-cookie security. Legacy `/api/openapi.json` returns the same generated
  document.
- Real Uvicorn HTTP smoke: `/health`, `/docs`, `/redoc`, `/openapi.json`, and
  `/ready` each returned `200`; structured request/shutdown logs were observed.
- Reference JSON importer: clean schema plus frozen fixture restored core entities
  and passed regression assertions.
- Final architecture scan: no API/application-to-infrastructure or ORM imports;
  reference checkout remains read-only with no tracked working-tree changes.

## Environment-only verification

- PostgreSQL migration integration was verified against a temporary PostgreSQL
  16 container. Deterministic API tests use SQLite/local storage/log email/
  in-memory limiter; the new adapter test exercises the ClamAV `PING`/`INSTREAM`
  protocol with a fake daemon.
- `docker compose config --quiet` passes and resolves API, PostgreSQL, Redis,
  MinIO, bucket initialization, ClamAV and Mailpit. A full image build reaches package
  metadata successfully but this environment's Docker network cannot complete
  TLS downloads from PyPI (`SSLEOFError`); the Dockerfile/package discovery issue
  was fixed. The dependency-stack pull is likewise blocked by the local Docker
  daemon proxy refusing `registry-1.docker.io:443`; no containers were created.
