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

`docker compose up --build` starts the API with PostgreSQL, Redis, MinIO,
ClamAV and Mailpit. The API container runs `alembic upgrade head` before
Uvicorn. MinIO creates the `lug` bucket through the one-shot `minio-init`
container; its console is at `http://localhost:9001`. Mailpit's inbox is at
`http://localhost:8025`. Uploads use the ClamAV network scanner and email uses
SMTP on port `1025`.

For production, replace these local dependency containers with managed/private
S3, ClamAV and SMTP equivalents through the typed environment settings. Do not
reuse the development credentials from Compose.

## Logs and incidents

Logs are JSON and include `request_id`, `trace_id`, HTTP method/path/status and
duration. Sensitive values are redacted. Search by request ID first, then check
`/ready` and dependency logs. A failed email delivery does not roll back a
committed registration; resend the verification code or inspect SMTP health.

Do not expose `/metrics`, `/ready` or admin routes publicly without the configured
operations/admin controls.
