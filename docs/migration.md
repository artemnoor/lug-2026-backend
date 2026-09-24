# Migration strategy from the reference backend

The reference persisted development state in `data/lug.json` and had a separate
PostgreSQL schema. The rebuilt runtime does not read that JSON file. Migration is
an explicit one-time import into the new relational schema:

1. freeze writes to the reference application and take an immutable JSON backup;
2. run `alembic upgrade head` against an empty target database;
3. import settings, teams, users, uploads, achievements and notifications in that
   order, preserving IDs and already-hashed passwords;
4. do not import active sessions or pending verification/reset codes — force a
   new login/verification flow;
5. verify foreign-key counts, unique emails/groups, ownership of file URLs and
   admin presence;
6. switch the frontend to the new API and keep the reference backup read-only
   for rollback/audit.

The legacy scrypt password format is accepted by the new login adapter and is
rehashed to Argon2id after a successful login. Files are not copied through an
HTTP request: storage keys must be migrated with a private object-storage copy
and then reconciled against `uploads` rows. Pending or unscanned objects are not
made readable by the new API.

The endpoint-by-endpoint status is maintained in
[`compatibility-matrix.md`](compatibility-matrix.md); no reference capability is
silently dropped. The current import remains a controlled operational step rather
than a startup side effect.
