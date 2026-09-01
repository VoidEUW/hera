# hera-providers

The model boundary. Everything that knows how to talk to a language model lives here, and
nothing that knows what a chat, a prompt or a tool *is*.

What leaves this package is **one normalised event union**. `hera_chats` persists it,
`apps/core` serialises it to Server-Sent Events, and the browser reduces it into a message — so
a new kind of thing the model can do is one new variant in `events.py`, not a new parser
somewhere above. The previous version of Hera had a parser on the server and a second one in
the browser that had to stay byte-compatible with it; this union is what that cost bought.

## Installation

Inside this workspace, depend on it by name — uv resolves it to the member:

```toml
dependencies = ["hera-providers"]
```

Outside, it installs like any package (`uv add hera-providers`); pin a compatible range,
`hera-providers>=0.1,<0.2`.

## Quick start

```python
from hera_providers import ChatMessage, ChatRequest, OpenAICompatibleProvider, Role, TextDelta

provider = OpenAICompatibleProvider()          # HERA_PROVIDER_* from the environment
request = ChatRequest(
    model=provider.settings.model,
    messages=[ChatMessage(role=Role.USER, content="Why is the first turn slow?")],
)

async with provider:
    async for event in provider.stream(request):
        if isinstance(event, TextDelta):
            print(event.text, end="")
```

## The event union

| Variant | Carries |
| --- | --- |
| `TextDelta` | a fragment of the visible answer |
| `ThinkingDelta` | a fragment of the reasoning channel |
| `ToolCallReady` | one complete tool call: `id`, `name`, parsed `arguments` |
| `TurnEnd` | `reason` (`stop`, `length`, `tool_calls`, `cancelled`) and optional `Usage` |

Every variant carries a literal `type`, so the union discriminates on the wire as well as in
Python. `EVENT_ADAPTER` validates and dumps one event — persist and re-read through it rather
than through each variant, so round-tripping stays a property of the union.

A stream always ends in exactly one `TurnEnd`, including when the server never reported a
finish reason.

**Reasoning stays a separate channel all the way up.** It is displayed differently, and it must
never be fed back into the next turn as if it were the answer.

## What the Qwen adapter absorbs

`QwenAdapter` is pure — no I/O, nothing async — and is the only place a model family's quirks
are allowed to live. Supporting another family is a new `StreamAdapter` and nothing else.

**Reasoning arrives two ways.** Depending on the server and its chat template, the same model
reports reasoning either in a `reasoning_content` field beside `content`, or inline in
`content` wrapped in `<think>` tags. Both are lifted into `ThinkingDelta`, so no layer above
ever sees a tag or has to know which server it is talking to.

The awkward part is that a tag can be split across chunks — `"...<thi"` then `"nk>..."` — so
text is only released once it is certain not to be the start of one. The accepted cost: a model
that writes the literal string `<think>` in its prose has that treated as a tag. Nothing can
tell the two apart in a stream.

**Tool calls arrive in fragments** indexed by position, with the arguments streamed as partial
JSON. They are accumulated here and emitted whole, in index order, at the end of the turn.
Several at once is the normal case, not the corner — parallel calls are why a whole turn's
worth of independent lookups costs one round-trip.

**A turn that ends in calls says so.** Some servers report `stop` alongside tool calls; the
reason is normalised to `tool_calls`, because that is what decides whether the loop runs again.

## Errors are raised, not emitted

An error is not something a model emits, so the union stays exactly the set of things that
are. The layer owning the turn catches these and decides what to persist — it is the only one
that knows how much of the answer already arrived.

| Error | Means |
| --- | --- |
| `ProviderUnavailable` | nothing is listening. The most common failure of a self-hosted setup |
| `ProviderTimeout` | reached, but too slow. A different remedy: a longer timeout, not a restart |
| `StreamInterrupted` | it answered, then the connection broke mid-answer |
| `ProviderHTTPError` | a non-success status, carrying `status_code` and `body` |
| `MalformedResponse` | a shape this package cannot read |

Nothing from httpx escapes — a raw `RemoteProtocolError` reaching the turn loop would be an
unhandled crash exactly where a persisted partial answer belongs. `StreamInterrupted` has its
own name because the response differs: the events already yielded are real. A local server
killed part-way through generation is the usual cause, and what arrived should be persisted
with a `cancelled` turn rather than discarded.

**One thing that is deliberately not an error:** a tool call whose arguments are not valid
JSON. That is the model being wrong rather than the server, and it travels as
`ToolCallReady.parse_error` with the text kept in `raw_arguments`. One bad call must not
discard the calls that arrived beside it, and the turn stays alive: the layer above can feed
the error back as a tool result and let the model correct itself.

Embeddings raise like anything else. A caller that would rather degrade than fail — retrieval
falling back to keyword overlap — catches `ProviderError` and decides there, because whether a
missing vector is fatal is not a question this package can answer.

## FakeProvider

The load-bearing test tool of the project. Every layer above is exercised against it, so none
of them needs a model running; anything genuinely needing a live endpoint is marked
`@pytest.mark.live` and stays out of CI.

```python
from hera_providers import FakeProvider, text_turn, tool_call, tool_turn

provider = FakeProvider([
    tool_turn(tool_call("hera__search", {"query": "qwen3.6 release date"})),
    text_turn("Because ", "the weights are cold."),
])
```

A script is either a list of turns, consumed one per `stream()` call, or a callable that
decides each turn from the request it is given — which is how a tool loop gets driven: turn one
asks for a tool, turn two sees the result and answers. A turn may also be an `Exception`, which
is raised instead of streamed; that is how the error paths get tested without a broken server.

Running past the end of the script raises `FakeProviderExhausted` rather than repeating the
last turn: a loop asking for more turns than were scripted is a bug, and answering it again
would hide exactly that. Every request is recorded on `provider.requests`, so assert against
what was sent instead of reaching for a mock.

`embed()` returns deterministic unit vectors derived from a hash. They carry no meaning, which
is the point — they make the plumbing around retrieval testable without implying a similarity
that is not there. Pin the vectors a test actually reasons about with
`FakeProvider(embeddings={...})`.

## Settings

`HERA_PROVIDER_*`, describing the intended deployment: a local OpenAI-compatible server, no
authentication, one Qwen model.

| Setting | Default |
| --- | --- |
| `base_url` | `http://localhost:1234/v1` |
| `api_key` | empty — most local servers reject a bearer header they did not ask for |
| `model` | `qwen3.6-35b` |
| `embedding_model` | empty, meaning embeddings are off |
| `timeout_s` | `180.0` — a local server may load a 35B model on the first request |
| `connect_timeout_s` | `5.0` — "nothing is listening" should be answered immediately |

## What does **not** belong here

No chats, no prompts, no tools, no memory, no persistence and no orchestration — this package
emits events and takes requests, and the loop around them lives in `hera_chats`. No text call
grammar and no output normalisation for a weaker model: both existed in the previous generation
purely to compensate for a 20B model, and both cost a second parser in the frontend. See
[ADR 2](../../docs/adr/0002-qwen-only-target-model.md).

`ChatRequest.extra` is merged into the request body last and is the seam for anything a
particular server understands and this package does not need to know about —
`reasoning_effort`, a sampler setting, a vendor flag. Guessing at those fields here would put
provider specifics back into the shared vocabulary.
