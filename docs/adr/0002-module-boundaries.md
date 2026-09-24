# ADR 0002: Business-domain boundaries

## Decision

Use `auth`, `users`, `teams`, `media`, `portfolio`, `video`, `notifications` and
`content` as business modules. Keep `admin` as an HTTP/application façade over
those modules plus read-only organizer queries.

## Rationale

These boundaries follow distinct ownership and authorization rules recovered from
the reference API. Technical folders such as a project-wide `services/` or
`repositories/` would hide those boundaries and recreate the reference coupling.
