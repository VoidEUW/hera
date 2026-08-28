# What she should be able to reach for

Notes, not decisions. Everything here is a shape argued for on the strength of using the build,
and none of it is settled — nothing below has an ADR, and several of these want one before any
code is written. `docs/frontend.md` is the model: a document you argue with, until the argument
is over and it becomes a rule somewhere else.

**Last updated:** 2026-08-28 · §§ 2, 3 and 5 have decision records now — 12, 15 and 13

The item that started this page — *she cannot look anything up* — is now done: `hera__search`
exists and § 1 is kept as the reasoning behind its shape rather than as a request. What is left
is `fetch`, and then everything below it.

---

## 1. Search — ✅ done, and `fetch` is not

**`hera__search` is built.** A `Searcher` port in `hera_mcp`, `hera_core.search.DuckDuckGo` as
the adapter, wired in `hera_core.wiring`. No key, so a fresh install can search. The rest of this
section is the reasoning that produced that shape, kept because the *next* tool here — `fetch` —
has to answer the same questions and gets different answers to some of them.

The problem it solved: for an assistant answering questions about anything that changed after the
weights were frozen, no search is not a missing feature, it is *the* missing feature — and it is
worse than absent, because a model with no search does not say "I cannot look that up", it
guesses fluently.

**Where it goes was the first question, and it was not obvious.** Two readings:

- **In `hera_mcp`.** Search is part of what Hera *is*, the way `remember` is. It gets the same
  port treatment: `hera_mcp` declares a `Searcher` protocol next to `MemoryWriter`, and the
  application injects whatever this deployment has. `hera_mcp` still imports no `hera_*` package
  and still knows nothing about a provider or an API key.
- **As somebody else's MCP server** in `~/.hera/mcp.json`. Zero code, works today, and it is the
  answer ADR 4 gives for every other capability.

The second is genuinely tempting and probably still wrong. A search tool she has *always* has to
be described in her prompt in her voice, has to have a result shape the activity gutter can draw
properly, and has to be there on a fresh install with nothing configured. The third of those
decides it: "install a gateway first" is not an acceptable answer to "why did she make that up?".

So: **a port in `hera_mcp`, an adapter in the application** — which is what was built. Swapping
DuckDuckGo for SearXNG or for something with a key behind it is a class in `hera_core.search` and
one line of wiring, and nothing in her tool description changes, because nothing in it names an
engine.

Two tools, not one, and the split matters. Only the first exists:

| | |
|---|---|
| `hera__search(query, limit)` | **Built.** Results as a list: title, URL, and the snippet the engine returned. Cheap, and it is what she calls when she does not know which page she wants |
| `hera__fetch(url)` | **Not built.** One page, as text she can read. Expensive in tokens, and it needs a length ceiling and a story for what happens when the page is 200 KB of navigation |

What was settled along the way, and what `fetch` still has to answer:

- **Which backend by default** — settled as DuckDuckGo, on the one criterion that mattered:
  anything requiring a key means a fresh install still cannot search, which is the problem this
  existed to solve. `ddgs` is a scraper and will break; the `live`-marked test in
  `apps/core/tests/test_search.py` is the only thing that will notice, and it does not run in CI.
- **Search is allowed, fetch probably is not.** The default policy allows `hera__*` outright, and
  `search` is the first of her tools that leaves the machine. It stays allowed because a card
  before each of the three or four lookups a real question takes would be exactly as unusable as
  one per emotion, and a search *reads* something public and changes nothing. A fetch is a
  different act: `http://192.168.1.1/` is a request to a machine somebody chose. That is a rule
  about the **argument**, and it belongs in `hera_permissions` rather than in the tool.
- **Extraction is still open.** A fetched page is HTML and she should be given prose. This wants a
  real readability extractor, not a tag stripper, and it is the same problem as the PDF one below
  — which is an argument for one "turn this document into text" seam serving both.
- **Nothing found is not a failure.** Learned while writing it and worth keeping: a model told
  the search is broken stops searching, and a model told nothing was found tries other words. The
  two answers come back differently on purpose.

---

## 2. Notes as a scratchpad, per chat — ✅ decided, as [ADR 12](adr/0012-a-chat-has-a-scratchpad.md)

**The open questions below are answered there.** In short: a **directory** per chat at
`~/.hera/chats/<chat id>/scratch/`, not one `NOTE.md` — settled by § 3's sandbox, which needs a
working directory with several files in it. The person does **not** see it, so it is a cache and is
said to be one: deleting a chat deletes it. It does **not** survive into the prompt; she calls
`hera__scratch_list` when she wants to know what she left herself, which keeps the context-budget
question with the compaction work where it belongs. And `hera__note` keeps the description it has,
so the two stop overlapping.

What that section did not see coming is the thing that turned out to block it: **no tool could know
which chat it was in.** Her server is built once at startup and `hera_tools` runs every call as a
child of a worker task created at *connect* time, so the obvious `contextvars` answer reads back
empty and does so silently. It goes in MCP's `_meta` instead. That mechanism is the reason this
section had to be built before §§ 3 and 5 rather than merely before them in taste.

The last paragraph below was right and cost nothing to honour: writing and reading share the quill.

<details>
<summary>The original argument, kept for the reasoning</summary>

## 2. Notes as a scratchpad, per chat

`hera__note` writes "a document into the notes the person keeps", and `NoteWriter` is unwired.
In practice she reaches for it as **working memory** — somewhere to put a plan, an intermediate
result, a list of what she has checked so far — which is not what the description asks for and
not what a person's notes vault is for. Two different things are wearing one name.

The proposal is to take the observed behaviour seriously rather than correcting it:

```
~/.hera/scratchpads/<chat id>/NOTE.md
```

One directory per conversation, hers to write, hers to read back, and it lives exactly as long
as the conversation does. That gives a turn somewhere to put more than fits in a tool result and
gives the *next* turn a way to pick it up without the whole thing being replayed through the
context window — which is the actual win, and the reason this is worth building rather than
telling her to stop.

What it needs decided:

- **Is it one file or a directory?** `NOTE.md` as written is one file, which is simple and gets
  clobbered the moment she wants two. A directory with free filenames is a small filesystem and
  wants read, write and list — three tools, and at that point it is closer to `hera-code-mcp`
  below than to `note`.
- **Does the person ever see it?** If yes it is a panel in the interface and part of the design
  language. If no, it is a cache and should be said to be one, and cleaning it up when a chat is
  deleted is not optional.
- **Does it survive into the prompt?** The tempting version injects the scratchpad into every
  turn of that chat, which is a context-budget decision and belongs with the trace compaction
  work in v0.2, not here.
- **`note` versus the scratchpad.** If both exist, `note` keeps the description it has — a
  document for the person — and the scratchpad gets its own name and its own sentence. Two tools
  whose descriptions overlap is how a model ends up choosing at random.
- **The gutter is already ready for it.** `Quill.svelte` is the mark for *she wrote something
  down*, mapped in `$lib/tools`'s `mark()`. Whatever the scratchpad tools end up being called,
  drawing them is one line there — and writing to it and reading it back should share the quill
  rather than split, because the reader's question is *did she write something down*, not which
  call carried it.

</details>

---

## 3. Three MCP servers, eventually

Today there is one server she *is* and one client she *has* (`CLAUDE.md` is emphatic about the
difference, and it stays true here). The proposal splits the server side three ways:

| | |
|---|---|
| **`hera_mcp`** | What makes her Hera: stance, memory, notes, skills, and search. Exists |
| **`hera_code_mcp`** | The tools a coding task wants — reading and editing a tree, running a build, reading diagnostics. Later |
| **`hera_sandbox`** | Somewhere to actually run the code. **Decided** — [ADR 15](adr/0015-running-code-in-a-container.md), shipping as `hera-sandbox-mcp` in v0.2 M2c |

`hera_code_mcp` is still later, and the sandbox does not smuggle it in: `sandbox__run` runs one
command over one directory and knows nothing about a repository.

The reason to write it down now is the *boundary*, because getting it wrong is expensive later:
these are three servers, not three sections of one, and the client mounts each under its own
name (`hera__`, `code__`, `sandbox__`). A person who does not want a coding agent does not mount
the second, and her prompt does not describe tools she does not have. That falls straight out of
how `ToolRegistry` already works and costs nothing to preserve — but only if `hera_code_mcp` is
never allowed to start life as four more `@server.tool`s inside `hera_mcp`.

`hera_sandbox` is the one with a real question in it: it is the only component in this project
that would run code somebody else wrote, and "small sandbox for testing" and "safe" are not the
same claim. A container with no network and a mounted scratch directory is the cheap version.
Anything stronger is a project. It should not be built until somebody has written down which of
those two it is.

**Somebody has.** [ADR 15](adr/0015-running-code-in-a-container.md) answers *the cheap version,
built carefully* — no network, read-only root, dropped capabilities, a non-root user, memory, pid
and cpu ceilings, a host-side timeout, and never the Docker socket. It says plainly that a shared
kernel means this is not a defence against a container escape, and names what would upgrade the
claim. The paragraph above was not a delay, it was a demand for that record, and building the
sandbox is what writing it unblocked. The "mounted scratch directory" guessed at here is § 2's,
which is the other reason these two are one piece of work.

---

## 4. `hera__emotion` should be able to ask — ✅ done

**Built, as `hera__ask` rather than as a flag**, and it did generalise the permission path rather
than sitting beside it — which is what the rest of this section argued for and is the part worth
keeping. What was decided, against the open questions below:

- **A separate tool, not an argument.** `hera__ask(question, kind)`. The reasoning below holds:
  descriptions are prompt text and one clear sentence beats a conditional.
- **Asking ends the turn**, exactly as a permission card does. `AnswerRequired` closes the turn
  with `awaiting_answer`, the events persist, and `POST /chats/{id}/answers` resumes the *same*
  assistant message. The reply becomes the `tool_result` for that call — so nothing on the
  model's side of the loop learns a person was in it.
- **Nothing new suspends a turn.** `hera_chats` does not know `hera__ask` exists: it takes
  `ChatsSettings.asking_tools`, and the application fills it in from `hera_mcp.ASK_TOOL`. A
  deployment that configures nothing runs the tool normally, and the server refuses it.
- **Nobody answering is the permission path's answer.** The turn is closed and resumable; there
  are no timeouts.
- **What it costs when overused** is answered in the mind rather than in code — the `uncertainty`
  region says when a question is worth asking, and it is evolvable, so the useful version is
  learned from conversations that went badly.
- **Laurel, not brass.** Brass is authority: *this needs a decision*. A question is her turning
  towards you, which is the emotion card's register.

**One thing this uncovered.** Both this section and `docs/status.md` said the composer "already
blocks while `awaiting` is non-empty". It did not — nothing read that field. Sending past an open
card writes a fresh assistant row, and the resume routes work from `latest_assistant`, so the
suspended turn was orphaned and its card could never be answered. Fixed with the feature, and
`busy` and `blocked` are now separate: a suspended turn is not a running one, and offering
**Stop** for something that already stopped is a lie about what is happening.

<details>
<summary>The original argument, kept for the reasoning</summary>

## 4. `hera__emotion` should be able to ask

Today `emotion` is a statement: she shows a stance, the card renders, the tool returns `"shown"`
and the turn continues. `doubt` about slide 14 puts a card on the screen and then she carries on
as though she had not doubted anything.

The proposal is that a stance can be a **question**, and that answering it is a thing a person
can do — the card grows a reply field, what is typed goes back as the result of that call, and
the turn continues with the answer in hand.

This is a bigger change than it looks, and the reason is worth stating: the plumbing already
exists. `permission_required` is exactly this — a card that suspends a turn, waits on a person,
and resumes with what they decided (`hera_chats.turn`, and the composer already blocks while
`awaiting` is non-empty). An asking emotion is the same mechanism with a different card and a
free-text answer instead of allow/deny. So the work is not "build a callback", it is "generalise
the one we have", and doing it the other way — a second suspension mechanism beside the first —
is the thing to avoid.

What has to be decided:

- **Is it a new tool or an argument?** `hera__ask(kind, text)` is honest and adds a fifth tool.
  `hera__emotion(kind, text, ask=True)` keeps one vocabulary and makes the card's behaviour
  depend on a flag, which is harder to describe to the model in one sentence. Leaning towards the
  separate tool, because the descriptions are prompt text and one clear sentence beats a
  conditional.
- **What happens when nobody answers?** A turn suspended forever is a turn that looks broken. The
  permission path already has an answer for this (`turn_closed` with `awaiting_permission`, and
  resuming later) and this should reuse it rather than inventing timeouts.
- **Does it block?** A stance that asks and then keeps talking is nearly useless; a stance that
  asks and stops mid-paragraph is jarring. Probably: she may ask, and asking ends the turn — the
  same shape as a permission card.
- **What does it cost when she overuses it?** `emotion` is described as something to call often.
  An asking version described the same way turns every answer into an interview.

</details>

---

## 5. Artifacts — ✅ decided, as [ADR 13](adr/0013-artifacts-are-tool-calls-with-versions.md)

Everything below held. A tool call, an event like everything else, a home in `hera_mcp`, and the
identity-and-versions part as the reason it is worth building at all. Three things the record adds:

- **The storage question the last paragraph insists on is answered first**, in § 2, and answering
  it is what let this one stay small. The content lives at `~/.hera/artifacts/<id>/v<N>.<ext>` with
  the row as an index — flat by id, so moving a chat between projects does not move files.
- **`from_scratch`**, which is create-and-update taking a filename in the chat's scratchpad instead
  of inline content. It exists because a `.pptx` a script produced cannot come back through a text
  tool result, and it is the concrete reason artifacts land before the sandbox rather than after.
- **A `file` kind**, for exactly that case: a name, a size and a download, rather than pretending
  to render a zip.

*"Do not build the executor first"* was right, and is still right — [ADR 15](adr/0015-running-code-in-a-container.md)
runs a command over a directory and knows nothing about a workflow.

<details>
<summary>The original argument, kept for the reasoning</summary>

## 5. Artifacts

Nothing in the system today can produce **a thing** — a document, a workflow definition, a
diagram, a small program — as an object with an identity, rather than as prose inside an answer
that a person then copies out of a code fence.

This is the largest item here and the least specified. What is clear:

- It is not a rendering trick. ADR 11 draws the line at typesetting: the browser sets her prose
  as Markdown and TeX and reads no meaning back out of it. An artifact that the interface
  *discovers* by looking for a fenced block with a filename in it would be a parser in the
  browser, which is the rule this project will not bend. So an artifact is **a tool call**, and
  it produces an event like everything else.
- It therefore has a natural home: `hera_mcp`, next to `note`, sharing whatever storage the
  scratchpad decision produces.
- The interesting part is **revision**. An artifact that can only be created is a file with extra
  steps; the value is in "change the third step" not re-emitting the whole thing. That means an
  identity, a version, and a diff — and a card in the conversation that shows the current state
  rather than the history of it.
- Workflows are the motivating case and are a special case of it: a workflow is an artifact whose
  content happens to be executable by something. Do not build the executor first.

Nothing here should start before the scratchpad question is answered, because they want the same
storage and answering them separately produces two.

</details>

---

## 6. PDFs — in scope for v0.1.0

**Decided:** reading PDFs is in v0.1.0. **Not decided:** where the extraction happens.

Today `attachments.ts` refuses anything that does not decode as text and says so, which is the
correct behaviour and not a good enough one — a paper, a spec and a scanned invoice are all
ordinary things to put in front of her.

Two places it can happen, and they are a real trade:

- **In the browser, with `pdfjs-dist`.** Keeps the whole "read in the browser, sent as a field"
  design intact: a PDF becomes text before it leaves the page, so it travels through the pipeline
  that exists and works against any endpoint, vision or not. Costs a heavy dependency in the
  bundle.
- **Server-side, with `pypdf`.** Cleaner separation and no bundle weight, but there is no upload
  endpoint today, so it means adding one plus a bytes field on `AttachmentIn` — and an upload
  endpoint is a thing `docs/status.md` currently says is deliberately absent.

The browser is the better answer for v0.1.0 and the server the better one eventually, which
usually means doing the browser one and being honest that it moves later.

Either way, the same question the fetch tool has: a PDF is not only text, and a page of a scanned
document has no text at all. Extraction that silently returns an empty string for a scan is the
mojibake problem again in a new coat. It should say what it could not read.

---

## The order

Rewritten once v0.2 M2 took shape, because the dependencies turned out to run the other way from
how this list first guessed. The chain is **scratchpad → artifacts → sandbox**: none of the
artifact kinds need code execution, and what the sandbox needs is somewhere to put what it
produces.

1. ~~**Search.**~~ Done. ~~**Asking emotions**~~ — done, as `hera__ask`; it generalised the
   permission path, which is what § 4 said it should.
2. ~~**The scratchpad**~~ — decided, [ADR 12](adr/0012-a-chat-has-a-scratchpad.md), and it is v0.2
   M2a. It unblocks the two below by answering where a document lives, and by making a tool call
   able to know which chat it is in at all.
3. **Artifacts** — decided, [ADR 13](adr/0013-artifacts-are-tool-calls-with-versions.md), plus
   skill resources ([ADR 14](adr/0014-skill-resources-are-readable.md)). M2b.
4. **The sandbox** — decided, [ADR 15](adr/0015-running-code-in-a-container.md). M2c.
5. **Fetch**, which is the other half of search — she can find a page and cannot read it, which is
   a worse place to stop than either end. Wants the same *turn this document into text* seam as
   PDFs, and a permission rule about the **argument** rather than the tool.
6. **PDFs**, scoped for v0.1.0 and still roughly a day's work in the browser.
7. **`hera_code_mcp`**, which is the one thing on this page still without a record and should not
   be started early.
