# 10. The persisted stream wraps the provider union rather than extending it

- Status: accepted
- Date: 2026-08-27

## Context

`hera_providers.Event` is described in `CLAUDE.md` as *one event union*: the model boundary
defines what a model can emit, everything above consumes it, and a new kind of thing the model
can do is one new variant there rather than a new parser. That rule exists because the previous
version of Hera had a parser on the server and a second one in the browser that had to stay
byte-compatible with it forever.

Building `hera_chats` reaches the case `docs/status.md` flagged as the first real decision the
turn orchestrator makes. A turn contains things that are **not** model output:

- a **skill selection**, made in code before the model saw anything (ADR 5);
- a **tool result**, which comes back from an MCP server (ADR 4);
- a **permission request** and the answer to it, which come from a policy and a person.

All three have to be persisted and rendered. None of them is something a model emits.

Two options, both consistent with "no second parser":

1. **Grow the provider union.** Add `tool_result`, `skill_selected` and `permission_required`
   to `hera_providers.Event`. One union everywhere, no mapping at all.
2. **Wrap it.** `hera_chats` defines `ChatEvent`, re-using the provider's variants unchanged
   and adding its own.

## Decision

**Wrap it.** `hera_chats.events.ChatEvent` is the persisted and streamed union. `TextDelta`,
`ThinkingDelta` and `ToolCallReady` are re-used from `hera_providers` with their `type`
literals intact, so an event crossing the provider boundary crosses this one without
conversion.

Growing the provider union was rejected because it inverts the layering. `hera_providers` has
an empty allow-list in `tests/test_layering.py`: it knows nothing about chats, prompts or tools,
and that is what lets it be replaced or reused on its own. A `tool_result` variant would make
the model boundary carry a concept from `hera_tools`, a `skill_selected` variant would make it
carry one from `hera_skillsets`, and the package that must not know what a skill is would have
its shape decided by one.

Two consequences follow from the same reasoning:

**`TurnEnd` is not part of `ChatEvent`.** It is the model's full stop for one *round trip*, and
a turn that calls tools has several. Forwarding them all would make the interface work out
which one was last. The orchestrator consumes them, adds up their usage, and closes the turn
once with `turn_closed` — whose reason set is wider than a `FinishReason`, because a turn can
also be waiting for a person or have exhausted the tool loop.

**`ToolResultEvent` mirrors `hera_tools.ToolResult` rather than embedding it.** `hera_chats`
may import `hera_tools`, so embedding it would type-check; but the persisted event is read back
by `apps/core` and the browser, and pinning a stored row's shape to another package's model
turns every change there into a migration here.

## Consequences

- There are two unions and a **total, mechanical** mapping between them, in one place
  (`Turn._ask`). "No second parser" holds: neither union is parsed, both discriminate on
  `type`, and neither is derived from text.
- The frontend renders one component per `ChatEvent` variant and never sees the provider union.
  Its contract is `hera_chats`.
- A new kind of thing a **model** can do is still one variant in `hera_providers`, plus one
  line in the mapping. A new kind of thing a **turn** can contain is one variant here and no
  change to the model boundary at all.
- `hera_permissions`, `hera_skillsets` and `hera_tools` keep their own vocabularies. Nothing
  they own leaks into a stored row except as fields this package chose to copy — `failure` is
  stored as a plain string for that reason, so a value added upstream reads through instead of
  failing validation on an old row.
