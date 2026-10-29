# 32. What a person says is encrypted at rest, with the instance's key

- Status: proposed
- Date: 2026-10-29

## Context

With accounts ([ADR 27](0027-an-account-is-a-session-and-a-role.md)), `hera.sqlite3` holds every
person's conversations and the email they sign in with. Their secrets are already safe if the file is
copied: passwords are argon2id with a salt each, and sessions and one-time tokens are SHA-256 digests
of random values, which cannot be used to sign in. Everything else is plain text. A database file
that leaks, through a backup, a synced folder, a copied home directory or a disk sold on, gives away
every conversation on the instance and the address of everyone who has an account.

Hashing cannot help here, because hashing only goes one way. Hera has to read a conversation back
to draw it and to send it to the model. What helps is encryption, and every form of it comes with
the same limit: the server needs the key to read the data, so encryption protects data that has been
*taken away* from the server, and does nothing for a server that has been broken into.

Three shapes were considered:

- **The whole file, with SQLCipher.** Everything is covered, metadata included. But it needs a
  native SQLCipher build on Linux, macOS and Windows for the frozen desktop app
  ([ADR 29](0029-the-desktop-app-is-a-shell-over-a-frozen-hera.md)), and it does nothing for
  `HERA_STORAGE_URL` pointed at PostgreSQL.
- **Columns, with a key per person** unlocked by their password. Not even the host could read a
  signed-out person's chats. But a password reset would destroy them, a passkey-only account (M4)
  would need its own way to wrap the key, and dreaming on a schedule
  ([#256](https://github.com/VoidEUW/hera/issues/256)) could not read a person's chats while they
  are away.
- **Columns, with one key for the instance.**

Nothing in Hera queries chat text, titles or emails in SQL today. The palette and the rail filter
what has already been loaded, and `hera__search` searches the web. So encrypting those columns
breaks no query.

## Decision

**The columns that hold what a person wrote are encrypted with AES-256-GCM under one key per
instance.** Everything else in the database stays readable, accounts included.

| Encrypted | Left plain |
|---|---|
| `chat_chats.title` | ids, `owner_id`, timestamps, sequence numbers |
| `chat_messages.content`, `.events`, `.attachments` | the usage ledger: token counts and timings |
| `chat_projects.name`, `.instructions` | `account_users`: email, name, role, flags |
| | session and token digests (already one-way) |

- **Accounts stay readable, on purpose.** An encrypted email would have to be found through a keyed
  hash, and then everything about signing in would depend on the key: lose it, and nobody could sign
  in and no reset mail could be sent. Left plain, accounts, sign-in and password resets (by mail in
  M3, or `hera user reset-password`) never touch the key. A lost key then costs the conversations
  and nothing else. A copied database still gives away who has an account here; it no longer gives
  away what anybody said.
- **The key** is 32 random bytes in `~/.hera/secret.key`, written once with mode 0600 at the first
  boot. `HERA_SECRET_KEY` (base64) overrides it, for a deployment that keeps secrets outside the
  data directory.
- **The format** is `v1:` followed by base64 of the 12-byte nonce, the ciphertext and the tag. The
  table and column name are the associated data, so a value moved from one column to another fails
  to decrypt instead of being read as something it is not. The version prefix leaves room for
  rotating the key later.
- **The mechanism is a column type in `hera_storage`** (`Encrypted`, `EncryptedJSON`). Nothing in
  it is about Hera: it encrypts whatever it is given with a cipher the application hands to the
  `Database`. A model opts in per column. The type takes the cipher from the engine it is bound
  through, so two databases with two keys in one process (the test suite) never share one.
- **Files stay plain text.** Memories, the mind, artifacts, scratchpads, avatars, `config.toml`
  and `permissions.json` are files you are meant to be able to open, diff and back up
  ([ADR 16](0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md)). Disk encryption on the
  host is what covers them, and the documentation says so.
- **The key has a recovery form.** The setup wizard shows a **recovery key** once: the instance key
  written in groups of characters, like the setup code. It asks the admin to confirm they have
  stored it before it continues. `hera key show` prints it again on the host, where a shell is
  already the credential ([ADR 27](0027-an-account-is-a-session-and-a-role.md)).
- **A missing or wrong key stops the boot, and names two ways on.** It never shows ciphertext, and
  it never quietly makes a new key, which would leave the old conversations unreadable without
  anybody having decided that. The message offers:
  - `hera key restore`, which writes the recovery key back to `secret.key`;
  - `hera key replace`, which accepts the loss: a new key, and every conversation written under the
    old one is drawn as *encrypted with a key this Hera no longer has* rather than as an error.
    Accounts, projects' existence, and everything written afterwards work as before.

## Consequences

- Migration 0009 rewrites existing rows encrypted, and its downgrade decrypts them. Both need the
  key, so it is created before migrations run.
- **Losing the key and its recovery form together loses the conversations, and only them.**
  `secret.key` has to be backed up apart from the database, because a backup that holds both
  protects nothing. The recovery key is the copy meant to live somewhere else entirely, such as a
  password manager. `hera check` reports where the key is.
- A copied database, or a backup made without the key, shows who has an account and when they
  talked, but not what was said. A person with a shell on the host, and the key file, can still read
  everything. That is the line this decision draws, and a per-person key remains possible later as a
  second layer over this one.
- Searching message text in SQL is ruled out. A future search decrypts in Python, or keeps its own
  index under a key derived from this one.
- PostgreSQL deployments get the same protection, and the desktop app needs nothing native beyond
  `cryptography`, which already arrives with the MCP SDK and is declared explicitly from here on.
