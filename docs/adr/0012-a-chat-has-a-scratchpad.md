# 12. A chat has a scratchpad, and a tool call carries the chat it is in

- Status: accepted
- Date: 2026-08-28

## Context

Two problems that look unrelated turn out to be one.

**She uses `hera__note` as working memory.** [`tooling.md`](../tooling.md) § 2 recorded the
observation: `note` is described as *"a document into the notes the person keeps"*, and what she
actually reaches for it with is a plan, an intermediate result, a list of what she has checked so
far. That is not a notes vault, and the mismatch is not hers to fix — two different things are
wearing one name, and a model choosing between two overlapping descriptions chooses at random.

What she needs and does not have is somewhere to put more than fits in a tool result, that the
*next* turn can pick up without the whole thing being replayed through the context window. That is
the actual win: a long chat currently survives by re-reading itself.

**No tool can know which chat it is in.** `hera_mcp`'s tools are built once at startup with their
ports bound; `hera_chats` dispatches through `hera_tools`; and `ManagedServer` runs every call as a
child of a worker task created when the server *connected*. Python copies a context at task
creation, so the obvious answer — a `contextvars.ContextVar` set around the turn — reads back empty
in the tool, and does so silently. Anything per-conversation is blocked on this: the scratchpad,
artifacts ([ADR 13](0013-artifacts-are-tool-calls-with-versions.md)), the sandbox's working
directory ([ADR 15](0015-running-code-in-a-container.md)), and `hera__remember(scope="chat")`,
whose port has been shipping since v0.1 with a `scope` argument and no way to say *which* chat.

The tempting fix is to put `chat_id` in the tool's argument schema. It is the wrong one twice
over: the model does not know the id, so it would invent one, and a tool whose arguments include
something the caller must not choose is a tool with a forgery in its signature.

## Decision

**A scratchpad is a directory per conversation**, at `~/.hera/chats/<chat id>/scratch/`, reached by
three tools — `hera__scratch_write`, `hera__scratch_read`, `hera__scratch_list` — behind one
optional `Scratchpad` port in `hera_mcp`. `hera__note` keeps the description it has and stays
unwired; the two stop overlapping because one of them finally says what it is for.

**A directory rather than one file**, which is the question § 2 left open. The deciding argument is
[ADR 15](0015-running-code-in-a-container.md): a container running a script needs a working
directory with several files in it, and `NOTE.md` is clobbered by the second thing she wants to
write. Free filenames, no database row, no versioning — an artifact is what you get when you want
those, and it is a different record for that reason.

**A tool call carries its conversation in MCP's `_meta`**, not in its arguments and not in a
context variable.

- `ToolRegistry.dispatch` and `dispatch_all` take an optional `context: Mapping[str, str]` and
  forward it to `client.call_tool(..., meta=…)`. `hera_tools` never looks inside it: it is an
  opaque mapping the application filled in, exactly as `builtin` is a server object this package
  does not read.
- `hera_mcp` exports `CHAT_ID_META = "hera/chatId"` and its tools take a `ctx: Context` parameter,
  reading `ctx.request_context.meta`. The SDK **excludes `Context` from the tool's input schema**,
  so the model never sees the field and cannot fill it in.
- The two packages may not import each other, so they do not agree on the key — the application
  does, the same way it already resolves `hera_mcp.ASK_TOOL` into `ChatsSettings.asking_tools`.
  `ChatsSettings.chat_meta_key` is the new setting, empty by default, and empty means the turn
  sends no context at all.

**Nothing is injected into the prompt.** § 2 asked whether the scratchpad survives into every turn
of its chat; it does not. That is a context-budget decision and it belongs with the trace
compaction work, not here. She calls `scratch_list` when she wants to know what she left herself,
and the listing is three lines rather than a document.

**The person does not see it, and it is cleaned up.** § 2 said that if the answer is *no*, it is a
cache and should be said to be one — so it is said here: the scratchpad is hers, it is not a
feature of the interface, and deleting a chat deletes its directory. The gutter still shows that
she wrote something down, because *she wrote something down* is a fact about the turn; what is in
the file is not on screen.

## Consequences

- **`hera__remember(scope="chat")` becomes implementable** without any further work here, which is
  the sign the seam is in the right place. So does an artifact belonging to a conversation, and so
  does mounting the right directory into a container.
- **The mechanism survives the server leaving the process.** `_meta` is on the wire, not in
  process memory, so v0.3 serving `hera_mcp` over a transport of its own — and
  `hera-sandbox-mcp` running out-of-process from the start — need no second answer.
- **A foreign server receives the `_meta` too.** It is a namespaced key it will ignore, and the
  alternative — filtering by server name — would mean `hera_tools` learning which servers are
  hers, which is precisely the knowledge that package does not have.
- **A tool called outside a turn has no chat.** The three scratchpad tools raise a `ToolError`
  saying so rather than inventing a directory, which is what a caller reaching them over v0.3's
  transport deserves to be told. It is the same shape as `ask` refusing when nothing is running a
  turn.
- **Three tools rather than two.** Folding the listing into `read` with an empty name would be one
  fewer description at the cost of a conditional in prose, and this project has already decided
  that trade the other way once — `ask` is a separate tool from `emotion` for the same reason.
- **`~/.hera/chats/` is a new directory**, and it is the one every later per-conversation thing
  goes under. It contains only files a person can open in an editor, which is the promise
  `CLAUDE.md` makes about everything in that tree.
