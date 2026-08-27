# hera-chats

Projects, chats, the persisted event stream, and the turn.

```python
orchestrator = TurnOrchestrator(
    provider=provider, builder=builder, router=router, registry=registry
)

turn = orchestrator.begin(TurnContext(text="/tdd how do I test this?", profile=profile))
async for event in turn.stream():
    send_as_sse(event)

messages.record(assistant_message, turn.recorded, prompt_fingerprint=turn.prompt_fingerprint)
```

## The event union

`hera_providers.Event` says what a **model** can emit. A turn is bigger than that — a skill was
chosen before the model saw anything, a tool ran after it asked, a person was stopped and asked
whether it may — so `ChatEvent` wraps it rather than extending it. Three variants are re-used
unchanged, `type` literals intact; the rest are Hera's own.

| Variant | From |
|---|---|
| `text_delta`, `thinking_delta`, `tool_call_ready` | `hera_providers`, unchanged |
| `skill_selected` | the router, with **why** (ADR 5) |
| `tool_result` | the registry, including refusals and failures |
| `permission_required`, `permission_decided` | the policy, and the person |
| `turn_closed` | here — one terminator, always last |

`TurnEnd` is deliberately absent. It is the model's full stop for *one round trip*, and a turn
with tools in it has several; forwarding them all would make the interface work out which was
the last. The orchestrator consumes them and adds up their usage.

## Three properties

**Nothing raises into the caller's loop.** A dead provider, a broken stream, a model that will
not stop calling tools — each closes the turn with a reason. The consumer is an SSE response,
and an exception escaping mid-stream is a connection that just stops, which a browser cannot
tell from a network problem.

**Partial work survives.** `Turn.recorded` is complete at every moment, coalesced and ready to
persist, so a cancelled turn keeps the answer that did arrive.

**An `ask` stops the turn rather than blocking it.** The turn closes with
`awaiting_permission` and its events are persisted; answering the card starts a new turn that
resumes the same message. A turn holding an HTTP response open waiting for a person is a turn
that dies with the tab.

## Storage

A message stores its whole event list as JSON, coalesced — hundreds of streamed `text_delta`
events become one. That list is the source of truth: `content` is derived from it, the history
sent to the model is rebuilt from it, and the interface re-renders from it at `done`. Live view
and reload therefore cannot disagree.

Rebuilding history is the one piece of real work. A turn that called tools becomes an assistant
message carrying the calls, then one `tool` message per result, then a further assistant
message — flattening it loses the pairing between a call and its answer, and a model that
cannot match `tool_call_id` ignores the result silently. Thinking never goes back.

## Projects

A container with behaviour, not a folder: a name, instructions, pinned skills, a default
profile. `docs/frontend.md` holds the line against profiles — a profile answers *who she is*, a
project answers *what we are working on*. Project files are v0.2, because they need embeddings.
