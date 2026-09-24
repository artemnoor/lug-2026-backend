# Operations runbook

## Local

```powershell
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 4174
```

Use `/health` for liveness. In development `/ready` is available from loopback
without a token; it checks database, limiter and storage. `/metrics` is likewise
an operations endpoint.

## Docker

`docker compose up --build` starts the API with PostgreSQL and Redis. The API
container runs `alembic upgrade head` before Uvicorn. Volumes persist database
and local uploads. For production, replace local storage with S3 and provide
TLS/database, SMTP, secrets and a scanner through environment/secret management.

## Logs and incidents

Logs are JSON and include `request_id`, `trace_id`, HTTP method/path/status and
duration. Sensitive values are redacted. Search by request ID first, then check
`/ready` and dependency logs. A failed email delivery does not roll back a
committed registration; resend the verification code or inspect SMTP health.

Do not expose `/metrics`, `/ready` or admin routes publicly without the configured
operations/admin controls.
