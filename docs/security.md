# Security controls

## Request boundary

- `TrustedHostMiddleware` uses an explicit host allowlist.
- JSON and upload bodies have independent size limits.
- Compressed request bodies are rejected to keep size accounting predictable.
- State-changing browser requests require the double-submit CSRF token.
- Request IDs are accepted only with a bounded safe character set.

## Identity and access

- Passwords are never stored in pending registration payloads; only a password
  hash is retained.
- Sessions store token hashes, have an expiration, and can be revoked in one
  transaction.
- Login and sensitive upload/registration/password-reset endpoints use fixed-window
  limits; Redis is used when configured and memory is the deterministic local mode.
- Profile payloads have an explicit allowlist, so `role`, `teamId`, and other
  privileged fields cannot be mass-assigned.
- File reads check authenticated ownership/team/admin policy and clean scan status.

## Production requirements

Staging/production startup fails closed unless PostgreSQL with `verify-full`,
Redis, explicit hosts, a long operations token, private S3, SMTP, and a long
verification secret are configured. Default development admin credentials and
verification-code logging are rejected there.

Security regression coverage is in `tests/test_security_and_capabilities.py` and
the architecture test prevents API/application code from importing persistence
implementations.
