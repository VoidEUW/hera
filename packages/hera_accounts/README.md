# hera-accounts

Who is asking, and whether they are who they say ([ADR 27](../../docs/adr/0027-an-account-is-a-session-and-a-role.md)).

- **Users** with one of two roles, `admin` and `user`.
- **Passwords**, hashed with argon2id.
- **Sessions**: an opaque random token the caller hands to a browser, of which only the SHA-256
  is stored — so a copy of the database is not a set of live sessions, and signing out is a
  deleted row.
- **One-time tokens** with a purpose (`setup`, `invite`, `reset`, `launch`): single use,
  expiring, stored hashed the same way.

Imports only `hera_storage`, and knows nothing about HTTP. Turning a cookie into a user is the
application's job.
