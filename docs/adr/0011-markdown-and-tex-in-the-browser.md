# 11. Her prose is typeset in the browser, as Markdown and TeX

- Status: accepted
- Date: 2026-08-27

## Context

`CLAUDE.md` says **no second parser in the browser**, and `ARCHITECTURE.md` says the frontend
renders the event variants it is given. Both rules come from the same wound: the previous
version of Hera had a text call grammar, a parser on the server and a second one in the
browser, and every change to model output had to land in both on the same day or the interface
started dropping things it could no longer recognise.

The rules did their job. What they also did, read literally, was leave `text_delta` on screen
as a run of unstyled paragraphs split on blank lines. Against a real model that is not a
neutral choice:

- A model writes lists, headings, tables and fenced code because that is the notation prose is
  written in now. Shown raw, a table is a wall of pipes and a code block is prose with
  backticks in it.
- Qwen3.6-35B writes mathematics as TeX — `\(…\)` inline and `\[…\]` displayed. Unrendered, an
  equation is the one thing on screen a person genuinely cannot read.
- `---` is how a model marks a break in an argument. Rendered as text it is three hyphens;
  rendered as Markdown's *setext* heading it silently promotes the sentence **above** it to an
  `<h2>`, which is worse than either.

So the question is not whether to have a parser. It is where the parse happens: in code, once,
or in the reader's head, every time.

## Decision

**Typeset her prose in the browser** — `$lib/markdown.ts`, using `marked` for Markdown (GFM
tables, breaks on) and KaTeX for TeX, sanitised with DOMPurify before it reaches `{@html}`.

The rule the project actually cares about is about **structure**, and it stands unchanged:

> What she *did* never comes back out of text.

A tool call, an emotion, a skill selection, a permission request, an attachment — each is an
event variant with fields on it, produced above the model boundary and rendered by its own
component (ADR 10). Nothing in `markdown.ts` learns what any of those are, and no event is ever
reconstructed from prose. What it does is the opposite direction: it takes one string that a
model wrote *for a person to read* and draws it the way it was written. Typesetting is not
parsing for meaning, and conflating the two is what left equations on screen as source code.

Three details are decided with it:

**Setext headings are off.** `lheading` is disabled in the tokenizer, so `---` is always a
thematic break. A rule with air on both sides reads as a separator or as a gap between two
parts depending on what she meant by it, which is both of the things `---` is used for.

**A price is not a formula.** `$5 and $10` is far commoner in an answer than `$x^2$`, so the
`$…$` delimiter is accepted only when it opens and closes on a non-space and is not followed by
a digit. `\(…\)` needs none of that and is the delimiter to prefer.

**The output is sanitised, not trusted.** The string came from a model, and a model can be
talked into emitting a `<script>` by a page it was asked to summarise. KaTeX's MathML is kept —
it is what a screen reader reads — and links open in a new tab with `noopener`.

## Consequences

- The frontend gains one dependency set — `marked`, `katex`, `dompurify` — and one module that
  is pure: a string in, safe HTML out, testable without a browser.
- `render()` runs on every `text_delta` while a turn streams, on prose that is legitimately
  half-written. Markdown degrades into text on an open fence, an unpaired `$` or a half table,
  so a fragment renders as what it is so far and settles when the rest arrives.
- There is now exactly one place in the browser that turns text into markup, and it is not
  allowed to grow a second job. If a future feature wants to know something *about* the text —
  which skill it used, what file it means — the answer is still an event variant, not a regular
  expression here.
- Syntax highlighting is deliberately not part of this. It is a large dependency and a
  colour-scheme decision of its own; a fenced block gets the mono face, a border and its
  language class, and highlighting can land later without changing this seam.
