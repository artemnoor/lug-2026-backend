# ADR 0003: Business-shaped persistence ports

## Decision

Each module defines only the repository operations its use cases need. SQLAlchemy
adapters implement those ports; repositories flush but never commit. There is no
generic `Repository[T]` abstraction.

## Rationale

The reference used broad adapters and JSON payload fallback. Business-shaped
ports make queries and transaction expectations visible, avoid a leaky generic
wrapper, and allow a future adapter or service extraction without changing domain
rules.
