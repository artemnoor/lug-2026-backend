# ADR 0004: Preserve the observed HTTP contract

## Decision

Keep the reference `/api/*` paths, camelCase fields, cookie/CSRF names, status
codes and top-level `{error, code, details?}` envelope wherever code and frontend
consumers demonstrate them. Add generated OpenAPI and modern health aliases.

## Rationale

The existing frontend is a real consumer. Internal architecture can be rebuilt
without forcing a simultaneous frontend rewrite. Clearly unsafe file-read behavior
is intentionally tightened and covered by a regression test.
