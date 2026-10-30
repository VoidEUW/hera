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

## Amendment: invitations, resets and mail (M3)

- **An invitation makes the account.** It is created with no password, and its owner is sent a
  link (`invite`, seven days) to choose one. That works whatever the registration setting is,
  so `invite` needed a meaning of its own: **any signed-in person may invite somebody, as a
  user**. Admins invite anybody as either role, under every setting. `open` lets strangers
  register; `closed` leaves adding people to admins. There is no invite *code* to register with.
- **A reset never says whether an address has an account.** The request answers `202` either
  way, the mail goes out after the response so its timing is no clue, and every request counts
  against a throttle, because each one may fill somebody's mailbox. The link (`reset`, one hour)
  withdraws any earlier one, and using it signs that person out everywhere.
- **A link in mail an anonymous request caused is built from the public URL, or not sent.** A
  link built from the request's `Host` is one a stranger could aim at their own server. Without
  mail and a public URL, *forgot your password?* says to ask an admin, whose Users screen makes a
  reset link to copy. The token always sits after `#`, so no access log or `Referer` carries it.
- **`[mail]` lives in `config.toml`.** Host, port, `starttls · tls · none`, user, a write-only
  password, a sender and an optional sender name, which defaults to the instance's name. A
  `Mailer` port in `apps/core` sits over `smtplib`, so tests use a postbox instead.
- **A letter is plain text plus the same letter as HTML in the heaven theme**
  (`hera_core.letters`). The palette is copied from `heaven.css` and checked against it by a
  test. The HTML loads nothing remote: no font, no image, no pixel.
- **A link is always shown to whoever made it, with a copy button**, mailed or not, because mail
  can be slow or bounce after the server took it. *Copy a new link* makes one without mailing
  it. Only the token's digest is stored, so there is no earlier link to show again, and the new
  one replaces it.
- **Deleting a person deletes what they made:** their rows in every table and `users/<id>/`.
  Disabling is the way to keep it all. Nobody can delete or disable their own account, and the
  last admin cannot be removed.

## Amendment: passkeys (M4)

- **A passkey is added to an account, never the only way to make one.** It is registered on
  Settings → Account by somebody already signed in. Signing in with one needs no email, because
  passkeys are *discoverable*: the browser lists the keys it holds for this site, and the chosen
  key says whose account it is.
- **The relying party is the public URL's host, or the host the browser is at.** With a public
  URL set, passkeys are offered only to a browser actually at that host, since a key registered
  for `hera.example.com` from `localhost` is one the browser refuses. An IP address can't be a
  relying party, and a page that isn't a secure context (https or localhost) has no WebAuthn,
  so a Hera opened at `http://192.168.1.20` draws no passkey control at all. `/auth/state` says
  whether the server can name a relying party; the browser checks its own half.
- **A ceremony's challenge is remembered in memory**, single-use, for five minutes, and bound to
  the person who began it. A restart costs somebody one retry, which is cheaper than a table.
- **The signature counter is kept**, and one that goes backwards refuses the sign-in: that's a
  copied key. A key this Hera doesn't know and a key that didn't sign get the same answer, and
  failures count against the same kind of throttle as passwords.
