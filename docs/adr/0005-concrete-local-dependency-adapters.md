# ADR 0005: Concrete local dependency adapters

## Decision

Run MinIO, ClamAV and Mailpit in the local Compose environment and select them
through typed settings. The API talks to ClamAV over the `clamd` network
protocol, to MinIO through the existing S3 adapter, and to Mailpit through the
existing SMTP adapter. Keep command-scanner and log-email modes for deployments
that intentionally choose them.

## Rationale

Configuration-only seams left the most important integration paths untested and
made local behavior differ from deployment behavior. Concrete local services
keep the modular monolith simple while preserving infrastructure substitution:
managed S3, scanner and SMTP endpoints can replace the Compose services without
changing application or domain code. The bucket initializer and readiness checks
make startup ordering and dependency failures explicit.
