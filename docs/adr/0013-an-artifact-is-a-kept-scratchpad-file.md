# 13. An artifact is a scratchpad file she decided to keep

- Status: accepted
- Date: 2026-08-28

> **This record was rewritten before anything was built on it.** The first draft called an
> artifact *a tool call with an identity and versions*, backed by a new `hera_artifacts` package,
> two tables and `~/.hera/artifacts/<id>/v<N>.<ext>`. What changed is
> below under *What the first draft got wrong*. The convention this repository keeps — a decision
> that turns out wrong gets a superseding record rather than an edit — is about decisions with
> consequences downstream, and this one had none yet; the draft's reasoning is preserved in that
> section rather than deleted, which is what the convention is actually for.

## Context

Nothing in the system can produce **a thing**. A diagram, a document, a chart, a small program —
all of them arrive as prose inside an answer, and a person copies them out of a code fence.
[`tooling.md`](../tooling.md) § 5 called this the largest item on its list and the least specified.

Two things are wanted and they are not the same:

- **A file you can open and download**, listed somewhere you can get back to, shown in a pane
  beside the conversation the way every other chat application does it. A portfolio page, a
  document, a spreadsheet.
- **A figure inside the answer**, where she drew it. A flow chart explaining the thing she just
  described, a pie chart of the numbers in the paragraph above it. That is not a file you open
  later; it is part of the sentence.

The obvious implementation of the second is a rendering trick: watch the stream for a fenced
`mermaid` block and draw it. That is a parser in the browser and it is the one rule this project
does not bend — [ADR 11](0011-markdown-and-tex-in-the-browser.md) permits *typesetting* her prose
precisely because typesetting reads no meaning back out of it. A chart discovered by hunting for a
fence is meaning read back out of text.

## Decision

**An artifact is a file in this chat's scratchpad that she has marked as one.** Nothing more.

[ADR 12](0012-a-chat-has-a-scratchpad.md) already gives every conversation a directory she can
write to, read back and list. The distance between *a plan she left herself* and *a page you
want* is not a storage problem — it is one bit, and that bit is whether a person is meant to see
it. So:

```
~/.hera/chats/<chat id>/
  scratch/        every file she writes
  kept.json       which of them are artifacts, and what to call them
```

**One new tool: `hera__artifact_keep(name, title)`.** It marks a file she has already written.
Making a thing therefore reads the way it actually happens — write it, then decide it is worth
keeping — and the tool that writes a file stays the one tool that writes a file. `scratch_read`
and `scratch_list` need no change at all, because a kept file has not moved.

**No new package, no tables, no versions.** The whole feature is one JSON file, one tool, and a
panel. That is the point of the reframing and it is worth being explicit about what it costs:
**writing the same name twice replaces the file, and the previous content is gone.** There is no
v1/v2 and no diff. The value that was supposed to buy — *change the third step without re-emitting
the whole thing* — is not delivered by keeping old copies anyway; it is delivered by an edit tool,
which is deferred with its reasoning below.

### What the browser draws, and where

**Always a card where she kept it**, and the card is not a preview of a listing — it is the thing,
as far as the thing fits in a paragraph. The kind is derived from the **file extension**, so there
is no `kind` argument and no way for the model to disagree with its own filename:

| extension | in the conversation | in the pane |
|---|---|---|
| `.svg` | drawn inline, at figure width | full width |
| `.mmd` · `.mermaid` | rendered inline by `mermaid`, lazily imported | full width |
| `.html` · `.htm` | a framed preview, capped in height | full height, the whole page |
| `.md` | the first lines, set by `$lib/markdown` | the document |
| code and text | the fenced-code `figure` it already has, capped | the file |
| anything else | a name, a size and a download | a name, a size and a download |

That covers the second half of the request without a parser anywhere: a chart is an artifact whose
extension is `.svg` or `.mmd`, and it is drawn inline **because she made it there**, from an event,
not because something went looking for it in her prose.

**The pane is the enlargement, not a separate feature.** Clicking the card opens the drawer beside
the conversation; the drawer also carries the **file bar** — every kept file in this chat, newest
first, with a download on each. That drawer is the one [`v0.2.0.md`](../versions/v0.2.0.md) M3
planned to build once for three panels. It gets built here because this is the panel that needs
it, and memory and the dream log are shaped to fit it rather than the other way round.

### The HTML frame

`sandbox="allow-scripts"` and deliberately **not** `allow-same-origin`, so the frame runs with an
opaque origin: the page can execute its own JavaScript and cannot reach Hera's storage, cookies or
DOM.

**It can reach the network, and that is a decision rather than an oversight.** `sandbox` does not
stop a frame loading a font, an icon set or an image, and a page written without those looks
broken in a way that reads as Hera being broken — the request that produced the first real test of
this asked for Material icons by name. So a page she writes may fetch things, and may therefore
tell somebody it was opened. It is her own output rather than a page from the open web, which is a
materially smaller risk, but it is not zero and it is written here rather than discovered. A CSP
on the frame is the lever if that changes.

### No new `ChatEvent` variant

An artifact is a tool call and its result, exactly as an emotion is. `ToolResultEvent.structured`
already exists and is already `Any`; `artifact_keep` returns `{name, title, kind, bytes}` into it,
and the card is drawn from that while the content is fetched by name — so a 40 KB page never
bloats the stored message. Routing a tool name to a card is what `EmotionCard` already does, and
it is not a parser: `structured` is typed JSON the *server* produced.

### Deleting a chat deletes its artifacts

One cleanup path, the one ADR 12 already built. The confirmation says how many kept files go with
it, because *a chat is a thing you throw away* and *the page I made last week* have to be reconciled
by a sentence rather than by a surprise.

## What the first draft got wrong

Worth keeping, because two of the three are mistakes with a shape that recurs.

- **It invented a second store for something that already had one.** The scratchpad landed a day
  earlier and the draft still specified `~/.hera/artifacts/<id>/` beside it, with its own package
  and its own tables. `tooling.md` § 5 had warned about exactly this — *"they want the same storage
  and answering them separately produces two"* — and the draft answered it separately anyway.
- **It sold versions as the reason to build the feature**, and versions are not what anybody asked
  for. *An artifact that can only be created is a file with extra steps* was a good line about a
  bad requirement: the file is on disk, in a directory a person can back up, and the thing that
  makes revision cheap is an edit tool, not a pile of old copies.
- **It had no answer for a chart in the middle of a sentence.** It listed `mermaid` as a kind and
  put every artifact in a drawer, which is the wrong place for a figure that explains the paragraph
  above it.

## Consequences

- **`hera_mcp` gains one tool and one port**, not four and two. `ArtifactKeeper` alongside
  `Scratchpad`, and the adapter in `hera_core` is the same module that already owns the directory.
- **A diff-style edit is deferred, and now it is the *only* thing deferred.** Re-emitting a whole
  document to change a line is the real cost, and a tool for it is a v0.3 note with a reason. It is
  cheaper to add against this design than against the versioned one, because there is one current
  file to patch rather than a chain to append to.
- **`from_scratch` is gone, and so is the argument for it.** The bytes were already in the
  scratchpad; keeping them is a flag rather than a copy. The `.pptx`-from-a-sandbox case it was
  invented for lands the same way if [ADR 15](0015-running-code-in-a-container.md) is ever picked
  up, because the container's working directory *is* this directory.
- **A project's artifacts are the union of its chats'**, computed rather than stored. That is a
  directory walk over a handful of chats, and it is the correct amount of machinery for a list.
- **`mermaid` is a dependency and it is not small.** Imported lazily, so it stays out of the
  initial bundle and costs nothing until she draws one.
- **Nothing is versioned, and a person will eventually lose something to that.** Stated here so it
  is a known cost rather than a bug report: overwriting is what a file does.
