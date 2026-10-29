# 27. An account is a server-side session and a role

- Status: proposed
- Date: 2026-10-28

## Context

Hera has had a multi-user *seam* since v0.1 and no users. `current_user` returns `SINGLE_USER_ID`, a
constant. Every route takes it and most tables carry it as `owner_id`. What made this safe was the
bind address: `127.0.0.1`, one person, nobody else able to connect.

Both things v0.3.0 wants break that assumption. A Hera shared by a household or a team is reachable
by more than one person by definition. The desktop app's *connect to a server* mode exists to reach
a Hera on another machine. Both need to know who is asking, and some of what is asked
(adding an MCP server, which runs a command on the host) must be refused to most people.

The prototype had single-user auth: a PBKDF2 hash and an HMAC-signed cookie
(`docs/prototype.md` § *Auth & multi-device*). It worked, and it is not enough here. A signed cookie
cannot be revoked short of rotating the secret for everybody, and "sign this person out" is a
feature an admin needs.

## Decision

**A new package, `hera_accounts`, owns users, credentials, sessions and one-time tokens.** It
imports only `hera_storage` and knows nothing about HTTP. The application turns a cookie into a
user.

- **Two roles, `admin` and `user`.** No permission matrix. An admin manages the instance: users,
  model endpoints, MCP servers, the skill library, instance policy, mail. A user has everything that
  is theirs ([ADR 28](0028-what-belongs-to-a-person.md)). A third role waits until somebody needs
  one.
- **A session is an opaque random token** in an HttpOnly cookie (`SameSite=Lax`, `Secure` over
  https). The database keeps only its SHA-256, so a stolen database is not a set of live sessions.
  Signing out deletes the row, and "sign out everywhere" deletes all of a user's rows. **No JWT**,
  because revocation is the feature.
- **CSRF is an Origin check** on unsafe methods. `SameSite=Lax` already covers most cases, and the
  interface is same-origin by [ADR 6](0006-spa-over-json-sse-api.md), so there is no cross-origin
  client to allow.
- **Passwords are argon2id. Passkeys are WebAuthn**, with the relying party taken from the
  instance's public URL. A password is always possible, and a passkey is an addition, because
  WebAuthn does not exist on a plain-http LAN address and some self-hosted installs only have that.
- **One-time tokens have a purpose** (`setup`, `invite`, `reset`, `launch`). Each is single-use,
  expires, and is stored hashed.
- **Registration is `open`, `invite` or `closed`**, chosen by an admin.
- **`Owner` stays a `UUID`.** `current_user` changes what it reads, not what it returns, so route
  signatures do not churn. `Admin` is a second dependency beside it.
- **An existing install is adopted.** The first admin takes `SINGLE_USER_ID` as their id, so every
  existing row is already theirs.
- **A fresh server needs a setup code** printed to its log, unless the request is from loopback or
  carries a desktop launch token. Without one, a server exposed before its owner opened it belongs
  to whoever opened it first.

## Consequences

- `hera_accounts` joins the layering table with an allow-list of `hera_storage`, and migration 0008
  creates its tables. `core_accounts` (name, email) folds into `account_users`.
- Every e2e test and every script that talks to the API signs in first, as the prototype's did.
  The `FakeProvider` fixtures gain a signed-in client.
- A non-admin asking for an instance route gets 403. A user asking for another user's chat still
  gets 404, as `require_chat` already answers: "it isn't yours" and "it doesn't exist" stay the
  same response.
- Losing the only admin's password is not fatal: `hera user reset-password` runs on the host, and
  having a shell on the host is the credential.
