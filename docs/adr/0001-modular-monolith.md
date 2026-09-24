# ADR 0001: Modular monolith

## Decision

Deploy one FastAPI application with vertical business modules and explicit public
contracts. Do not split auth, portfolio, review or notifications into networked
services yet.

## Rationale

The recovered workflows share transactions, database ownership and request
authentication. A modular monolith keeps those operations atomic and easy to run,
while ports/contracts preserve a later extraction seam without pretending that
network boundaries already exist.
