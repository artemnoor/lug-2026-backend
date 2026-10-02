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

The single Compose file for the website and API lives in the root of the main
[`lug-2026` repository](https://github.com/artemnoor/lug-2026/blob/main/docker-compose.yml).
From that repository's root, copy `.env.example` to `.env`, set a local admin
password, then run `docker compose up --build -d`. The API container runs
`alembic upgrade head` before Uvicorn. MinIO creates the `lug` bucket through
the one-shot `minio-init` container; its console is at
`http://127.0.0.1:9001`. Mailpit's inbox is at `http://127.0.0.1:8025`.
Uploads use the ClamAV network scanner and email uses SMTP on port `1025`.
Use `docker compose down` to stop the services while preserving named volumes.

For production, replace these local dependency containers with managed/private
S3, ClamAV and SMTP equivalents through the typed environment settings. Do not
reuse the development credentials from Compose.

## Logs and incidents

Logs are JSON and include `request_id`, `trace_id`, HTTP method/path/status and
duration. Sensitive values are redacted. Search by request ID first, then check
`/ready` and dependency logs. Registration creates an account without sending
email. If a password-reset email is not delivered, inspect SMTP health and issue
a new reset request; a failed delivery does not roll back committed account data.

Do not expose `/metrics`, `/ready` or admin routes publicly without the configured
operations/admin controls.
