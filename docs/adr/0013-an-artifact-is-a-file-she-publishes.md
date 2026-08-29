# 13. An artifact is a file she publishes

- Status: accepted
- Date: 2026-08-29

> **Third draft, and the first two are summarised at the bottom** rather than deleted. One made an
> artifact a versioned object with its own package and tables; the other made it a scratchpad file
> with a bit set on it. Both were wrong in the same direction — they answered *where do the bytes
> go* and left *what is an artifact to a person* to fall out. It does not fall out.

## Context

Nothing in the system can produce **a thing**. A page, a document, a chart, a small program — all
of them arrive as prose inside an answer, and a person copies them out of a code fence.

Two shapes are wanted, and they are the two every chat application that does this well has:

- **A thing you open.** A card in the conversation — an icon, a name, *Artefakt*, an **Open**
  button — and a panel beside the transcript showing the rendered page, with a download.
- **A figure inside the answer.** A flow chart or a pie chart drawn where she drew it, because it
  explains the paragraph above it and is not something you go and open later.

The obvious implementation of the second is a rendering trick: watch the stream for a fenced
`mermaid` block and draw it. That is a parser in the browser and it is the one rule this project
does not bend — [ADR 11](0011-markdown-and-tex-in-the-browser.md) permits *typesetting* her prose
precisely because typesetting reads no meaning back out of it.

## Decision

**An artifact is a file in its own directory, and publishing it is a tool call.**

```
~/.hera/chats/<chat id>/
  scratch/        her working notes. Hers, nobody reads them (ADR 12)
  artifacts/      what she publishes. Named, rendered, downloadable
```

**Two directories, not one with a flag**, and the reason is the *scratchpad's*, not the artifact's:
ADR 12 promised that scratch is somewhere she can think out loud, unread and uncosted. The moment
a person browses that directory looking for the deliverable, every draft in it is on show and she
has a reason to be tidy in it — which is the one thing it was built not to need. Keeping them apart
costs one `mkdir` and keeps both descriptions honest.

**The filename is the identity.** `theme-workshop.html`, `flow.svg`, `report.md`. There is no id,
no row and no title field: the card's heading is the filename humanised — `theme-workshop.html` →
*Theme workshop* — by the same transformation `$lib/tools` already applies to `mcp-find`, and for
the reason written there: the author chose those words and a browser second-guessing them is how
one screen disagrees with the next.

**The extension is the kind.** `.html` renders in a frame, `.svg` draws, `.mmd` goes through
`mermaid`, `.md` is typeset, code is a fenced figure, anything else is a download. No `kind`
argument, so a model cannot disagree with its own filename.

### Three tools

| | |
|---|---|
| `hera__artifact_create(name, content, inline=False)` | Write it whole. Same name again replaces it |
| `hera__artifact_edit(name, find, replace)` | Change part of it without re-emitting the rest |
| `hera__artifact_read(name)` | The current content |

**`edit` is a find-and-replace, and that is the whole point of it.** A tool that took the full
content would be `create` with a different name, and a model choosing between two identical
descriptions chooses at random. More concretely: re-emitting a 40 KB page to change one colour is
minutes of generation, and it is what has actually been failing on the target endpoint. The
constraint that makes it safe is that `find` must match **exactly once** — zero matches and more
than one both come back as a readable error, because a replacement that hit the wrong one of three
is a silent corruption and the model cannot see the file to notice.

**`read` exists because `edit` is useless without it.** In a later turn the artifact's content is
not in the conversation — only the card is — so she has nothing to build a `find` out of. Without
`read`, every change is a full rewrite and the tool above buys nothing.

**`inline` is a property of the artifact, set when it is made.** True draws it in the conversation
where she made it, which is right for a diagram that explains what she is saying; false gives the
card with an **Open**, which is right for a page or a document. It is the model's call because the
model is the only one that knows which of those it meant — and it is a boolean it is *told about*
rather than something it has to notice, which is what [ADR 5](0005-deterministic-skill-routing.md)
actually objects to.

### No index, no tables, no versions

The directory is the store and there is nothing beside it. Everything a card needs — the name, the
`inline` flag, the kind — travels in the tool call and its result, which are already persisted
events; everything the file bar needs is a directory listing. `ToolResultEvent.structured` is
already `Any` and already exists, so this needs **no new `ChatEvent` variant**: routing a tool name
to a card is what `EmotionCard` already does, and `structured` is typed JSON the *server* produced
rather than text a model wrote.

**The content is fetched by name, never embedded in the message**, so a 40 KB page does not bloat
the stored event list. One consequence follows from that and is deliberate: **an artifact has one
current state, everywhere it appears.** Editing it in turn nine changes what the card in turn four
draws. A conversation is a record of what was *said*; an artifact is a file, and a file is what it
is now.

Nothing is versioned. Writing the same name twice replaces it, which is what a file does, and the
cost is stated rather than hidden: there is no undo, and `edit` is the reason that is bearable —
a targeted change is much harder to lose a document to than a full rewrite.

### The panel

Clicking a card opens a drawer beside the transcript: the artifact full size, a **Download**, and a
**file bar** listing every artifact in this chat. That drawer is the one
[`v0.2.0.md`](../versions/v0.2.0.md) M3 planned to build once for three panels — it lands here
because this is the panel that needs it, and memory and the dream log are shaped to fit it rather
than each bringing their own.

**An HTML artifact renders in a sandboxed `iframe`:** `allow-scripts` and deliberately **not**
`allow-same-origin`, so the frame has an opaque origin and cannot reach Hera's storage, cookies or
DOM. It *can* reach the network, and that is a decision rather than an oversight — `sandbox` does
not stop a frame loading a font or an icon set, and a page written without those looks broken in a
way that reads as Hera being broken. So a page she writes may fetch things and may therefore tell
somebody it was opened. It is her own output rather than a page off the open web, which is a
materially smaller risk, but it is not zero. A CSP on the frame is the lever if that changes.

### Deleting a chat deletes its artifacts

One cleanup path, the one ADR 12 already built. The confirmation says how many go with it, because
*a chat is a thing you throw away* and *the page I made last week* have to be reconciled by a
sentence rather than by a surprise.

## Consequences

- **Twelve tools on her own server**, up from nine, and that is the real cost of this record.
  Every one is a description the model reads before every turn. Three is the minimum that works:
  drop `read` and `edit` cannot be used; drop `edit` and every change is a full rewrite; drop
  `create` and there is nothing to edit.
- **`hera_mcp` gains one port**, `Artifacts`, alongside `Scratchpad`. The adapter is the same
  module in `hera_core` that already owns a chat's directory and already has the traversal guard —
  a name is checked the same way, and the test class that guard earned in ADR 12 is extended
  rather than copied.
- **They stay allowed by default.** All `hera__*`, writing inside `~/.hera` and reading inside it.
  The name guard is what makes that right, which is why it is a shared function rather than a
  second implementation.
- **The drawer arrives a milestone early**, which is a schedule change to M3 rather than extra
  work: it was always going to be built once.
- **A person will eventually lose an artifact to an overwrite.** Stated so it is a known cost. The
  file is on disk in a directory anybody can back up, and versioning it is a decision somebody can
  take later against a design that will not fight it.

## What the first two drafts got wrong

Kept because the mistakes have shapes that recur.

**Draft one — a versioned object.** A `hera_artifacts` package, `art_artifacts` and `art_versions`,
content at `~/.hera/artifacts/<id>/v<N>.<ext>`. It invented a second store a day after ADR 12 built
the first, which [`tooling.md`](../tooling.md) § 5 had explicitly warned about. And it sold
*versions* as the reason to build the feature, when nobody had asked for them: what makes revision
cheap is an edit tool, not a pile of old copies. That is the one idea from draft one worth keeping,
and it is `artifact_edit` above.

**Draft two — a scratchpad file with a flag.** Cheaper, and wrong about what the scratchpad is for.
Making the deliverable live in the notes directory means the notes directory is browsable, and a
scratchpad a person reads is not a scratchpad. It also read the wrong way round to a model: *write
a file, then decide it counts* describes bookkeeping, where *publish this* describes an act.

Both drafts also lost the same thing at the top of the page: what a person actually sees. A card
with a name and an **Open**, a panel with the page in it, and a chart drawn in the middle of a
sentence.
