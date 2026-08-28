# 13. An artifact is a tool call with an identity and versions

- Status: accepted
- Date: 2026-08-28

## Context

Nothing in the system can produce **a thing**. A diagram, a document, a workflow definition, a
small program — all of them arrive as prose inside an answer, and a person copies them out of a
code fence. [`tooling.md`](../tooling.md) § 5 called this the largest item on its list and the
least specified.

The temptation is to make it a rendering trick: watch the stream for a fenced block with a
filename on it, and draw a card. That is a parser in the browser, and it is the one rule this
project does not bend — [ADR 11](0011-markdown-and-tex-in-the-browser.md) permits typesetting her
prose precisely because typesetting reads no *meaning* back out of it. An artifact discovered by
hunting for a fence is meaning read back out of text.

There is a second reason it would not work even if it were allowed. The value is not in emitting a
document; it is in **changing the third step without re-emitting the whole thing**. An artifact
that can only be created is a file with extra steps, and a fence has no identity to update.

## Decision

**An artifact is a tool call**, and it produces an event exactly as an emotion does.

**A new package, `hera_artifacts`**, importing `hera_storage` and `hera_home` and nothing else.
Two tables, `art_artifacts` and `art_versions`.

**The content lives on disk**, at `~/.hera/artifacts/<id>/v<N>.<ext>`, with the row as the index.
`CLAUDE.md` promises that nothing in `~/.hera` is a format you cannot open in an editor, and the
first diagram you want to keep is where a SQLite blob breaks that promise. Flat by id rather than
nested under the chat, so moving a chat between projects does not move files.

**An artifact belongs to a chat and is listed at its project.** That is the second half of *a
project has its own context*, and it is why project folders came first.

**Three tools, behind one optional `ArtifactStore` port in `hera_mcp`:** `hera__artifact_create`,
`hera__artifact_update`, `hera__artifact_read`. Which chat they belong to arrives in `_meta`, per
[ADR 12](0012-a-chat-has-a-scratchpad.md).

**Create and update take `from_scratch` as an alternative to `content`** — a filename in this
chat's scratchpad, whose bytes become the version. This is the seam that makes
[ADR 15](0015-running-code-in-a-container.md) worth anything: a script that produces a `.pptx`
cannot hand it back through a text tool result, and without this the file would sit in a directory
nothing can reach. It is also the reason the scratchpad had to be decided first.

**No new `ChatEvent` variant.** `ToolResultEvent.structured` already exists and is already `Any`;
create and update return `{id, kind, title, version}` into it, and the card is drawn from that
while the content is fetched by id — so a 40 KB diagram never bloats the stored message. Routing a
tool name to a card is what `EmotionCard` already does. It is not a parser: `structured` is typed
JSON the *server* produced, not text a model wrote.

**Six kinds, and the last is the honest one:**

| kind | drawn with |
|---|---|
| `markdown` | `$lib/markdown.ts` and `Prose` — already exists, so nearly free |
| `code` · `text` | the fenced-code `figure`, with its caption bar and copy button |
| `mermaid` | `mermaid`, imported lazily so it stays out of the initial bundle |
| `html` · `svg` | a sandboxed `iframe`: `allow-scripts` and deliberately **not** `allow-same-origin`, so the frame has an opaque origin and cannot reach the application's storage |
| `file` | a name, a size and a download. What a `.pptx` is, and saying so beats rendering a wall of zip bytes |

**A diff-style edit is deferred**, with its reason: a fourth tool whose description overlaps
`update` is how a model ends up choosing at random, and tool descriptions here are prompt text.
Versions plus a rendered diff deliver the visible half of the value.

## Consequences

- **`hera__*` stays allowed by default**, and that stays right: these write inside `~/.hera` and
  read inside it. The guard that makes it right is the traversal check on `from_scratch`, so that
  gets a test of its own rather than a comment.
- **Revision is a real feature and costs a real table.** `art_versions` grows one row per update
  and one file per row; nothing prunes them, and a chat where she iterated forty times has forty
  files. That is the correct default for something described as *a thing you keep*, and pruning is
  a decision for whoever first minds.
- **Workflows fall out of this and are not built.** A workflow is an artifact whose content
  happens to be executable by something. `tooling.md` § 5 is right that the executor must not come
  first, and it does not.
- **The drawer is now needed.** Three panels want the space beside the conversation — artifacts,
  memory, the dream log — and this is the first of them. It gets built once, which is why the
  redesign milestone sits between this and memory rather than after both.
- **`file` is a load-bearing kind, not a fallback.** Without it, the script-running skills produce
  something the interface has to pretend to understand. With it, `pptx` works end to end the day
  the sandbox lands.
