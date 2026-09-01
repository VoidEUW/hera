# 3. Emotion cards are tool calls with an open vocabulary

- Status: **superseded by [17](0017-a-stance-is-a-sentence-and-a-question-stands-alone.md)**
- Date: 2026-08-26

> Kept as written, not edited. ADR 17 removed the feature after a version of driving it against a
> real endpoint — the vocabulary meant nothing to the model, and asking it to interrupt its own
> prose to file a small form is not a shape it complies with honestly. What this record got right
> is the part that outlived it: what she *did* is an event variant and never something parsed back
> out of what she wrote. That rule stands for every card in the interface.

## Context

Emotion cards are the feature that makes Hera feel like someone rather than something: alongside
her prose she shows a stance — agreement, doubt, a warning, a joke — as a small card with an icon
and a colour.

They were built as a text grammar: the model wrote `EMOTION doubt(text="…")` on its own line,
interleaved with prose. A server-side parser turned those lines into segments, and `stream.js`
re-implemented the same parser so the card could appear while the answer was still streaming. The
two had to agree on the regular expression, the canonical verb mapping, the prose capture rule
and the segment markup. Keeping them in sync was a standing instruction in the project notes,
which is a reliable sign that it kept failing.

The vocabulary was deliberately open — unknown verbs under the `EMOTION` prefix rendered as a
generic card — and that part was right, and is kept.

## Decision

`hera__emotion(kind, text)` is a tool on Hera's built-in MCP server.

- `kind` is free text. A starter vocabulary (`agree`, `disagree`, `doubt`, `surprised`, `funny`,
  `joke`, `warn`, `ask`, `curious`, `hope`, `excited`, `sorry`, `annoyed`, `judge`) is documented
  in the `emotions` mind region, explicitly as a starting point and not a cage; unknown kinds
  render with a fallback icon.
- The tool returns a minimal acknowledgement so generation continues.
- Several emotions in one turn are normal and cost **one** round-trip, because the target model
  emits parallel tool calls.

## Consequences

- One parser disappears. The frontend renders an event variant it receives; it never reads the
  model's text.
- An emotion costs a tool round-trip, where the text grammar cost nothing. With parallel calls
  and a tiny result payload this is one extra request per turn, which is acceptable next to the
  cost of generation itself.
- The system prompt must state that inventing a `kind` is allowed. The previous version learned
  this the hard way: a model that hard-obeys its system prompt will refuse to invent one unless
  the freedom is granted at system level, and a user turn cannot grant it.
- Emotions are reachable from any MCP client once Hera exposes her server, not just from her own
  chat loop.
