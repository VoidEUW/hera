# 28. What belongs to a person, and what belongs to the instance

- Status: proposed
- Date: 2026-10-28

## Context

With accounts ([ADR 27](0027-an-account-is-a-session-and-a-role.md)), every piece of state has to
answer *whose is this?*. Some of it already does: chats, messages, projects, usage, profiles and
skill usage carry `owner_id`, and their repositories filter on it. The rest has never been asked.
`~/.hera/memories/`, `~/.hera/mind/`, the avatar, `permissions.json`, `mcp.json`, `config.toml` and
`skills/` are one per install. `api/memories.py` takes the owner and ignores it, and `wiring.py`
builds one `MemoryStore` and one `MindRepository` for the process.

Three answers were possible:
- Only conversations are per person.
- Everything is per person, which is several installs sharing a process.
- The line in between.

Memories decided the first part on their own. A memory is *what Hera knows about you*, and every
enabled one is in the prompt ([ADR 16](0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md)).
A shared store would put one person's memories in front of another person's question.

## Decision

**A person owns their conversations, their memories and their mind. An admin owns everything that
runs code or costs money.**

| A person's | The instance's (admin-edited) |
|---|---|
| chats, projects, messages, artifacts, scratch | model endpoints (`config.toml`) |
| memories | MCP servers (`mcp.json`) |
| their mind (from the template) | the skill library, `trusted.json` |
| their usage | the mind **template**, and its policy regions |
| their own permission rules | the shipped and admin permission policy |
| avatar, name, sessions, passkeys | mail, registration, public URL |

- **Per-person files live in `~/.hera/users/<id>/`**: `mind/`, `memories/`, `avatar`,
  `permissions.json`. `hera_home.user_dir()` refuses a malformed id the way `chat_dir()` does.
- **The mind is cloned from a template.** `~/.hera/mind/` becomes the template an admin edits, and a
  new person's mind starts as a clone of it.
- **Two policy regions are not cloned.** `safety` and `tool_usage` are read from the template for
  everybody: instance policy, and a person's copy must not be able to remove it. `about_you`, also
  owner-fixed, is the person's, because it is about them. `write()` and `propose()` keep their
  tiers.
- **A tool learns whose memory it is from the chat**, carried in `_meta` exactly as
  [ADR 12](0012-a-chat-has-a-scratchpad.md) carries the chat. It never comes from an argument. The
  application resolves the chat's owner and hands the port that person's store.
- **Permissions are three layers**: the shipped policy, then the admin's file, then the person's. A
  person's rule can settle an *ask* and can never loosen a *deny* above it. "Always" on a card
  writes to the person's file.
- **Services build per-person pieces on demand.** `Services.for_user(id)` holds a small cache of
  mind repository, prompt builder and memory store. The turn takes its builder from `TurnContext`
  instead of holding one.
- **An admin cannot read other people's conversations or memories.** Managing accounts is not
  reading them.

## Consequences

- An existing install's `mind/` and `memories/` belong to the first admin (who takes
  `SINGLE_USER_ID`). The upgrade copies them to `users/<id>/`, and the existing `mind/` stays as
  the template, so nothing is lost and nothing is shared that was not before.
- `hera_profiles` needs a builder that composes two repositories (the person's and the
  template's), with region by region deciding which one answers.
- Dreaming ([#251](https://github.com/VoidEUW/hera/issues/251), [ADR 31](0031-a-dream-proposes-and-a-person-accepts.md)) becomes simpler: one person's chats, one person's
  mind, and `propose()` already refuses the regions they share.
- Skills are shared, so a skill one person writes is everyone's. That matches *a skill is code an
  admin installs*. Per-person skills are a later question if anyone asks it.
