# hera-prompts

A prompt compiler. It holds structured, serialisable prompt state and compiles it into
ready-made messages for a language model.

It knows nothing about tools, memories, skills or chats. Foreign content enters
exclusively as pre-rendered strings through named slots, which is what keeps this
library at the foundation layer: it imports no other `hera_*` package, does no I/O, and
has `pydantic` as its only runtime dependency.

## Installation

Inside this workspace, depend on it by name — uv resolves it to the member:

```toml
dependencies = ["hera-prompts"]
```

Outside, it installs like any package (`uv add hera-prompts`); pin a compatible range,
`hera-prompts>=0.1,<0.2`.

Linting, typing and tests are configured once in the workspace root and run from there:

```bash
uv run ruff check . && uv run mypy
uv run coverage run -m pytest && uv run coverage report
```

## Quick start

```python
from hera_prompts import Prompt, Role, Section

prompt = Prompt(
    sections=[
        Section(key="identity", content="You are Hera.", locked=True),
        Section(
            key="behavior",
            role=Role.DEVELOPER,
            children=[Section(key="behavior.character", content="You hold opinions.")],
        ),
        Section(key="request", role=Role.USER, slot="request", required=True),
    ],
    traits={"behavior.tone": "terse"},
)

result = prompt.render(bindings={"request": "Remind me how ablation worked?"})
```

The system message:

```
#IDENTITY
You are Hera.

#BEHAVIOR
BEHAVIOR tone = terse

#BEHAVIOR.CHARACTER
You hold opinions.
```

and the user message:

```
#REQUEST
Remind me how ablation worked?
```

## Three rules it lives by

**No domain knowledge.** A slot is a name and a string; what fills it is none of this
library's business.

**Everything is immutable and serialisable.** Every transformation returns a new object,
and a `Prompt` survives `model_dump_json()` and back without loss. Sections and traits
are stored in a normalised order, so two prompts built differently but holding the same
state share one `fingerprint()`.

**Determinism is a contract.** The same object plus the same bindings produces
byte-identical output.

## Messages are the frame, not the conversation

`render()` returns the system message(s) and the final user message. A chat history
belongs *between* them and is inserted by the calling layer — this library knows no
history, and `RenderResult.messages` is never a complete conversation.

## What locking means, and what an unknown key means

`replace()`, `remove()` and `set_enabled()` return the prompt **unchanged** when the
target section is locked, and `apply()` records a rejected change instead of raising when
a trait is locked. Refusing a change is a policy decision, and a caller that keeps running
into it is a signal the layer above wants to see — aborting would kill a whole run
instead.

An **unknown** key is a different matter: that is a caller error, and every method raises
`SectionError`. Use `is_locked(key)` to tell the two apart before acting.

The same line runs through the section tree: only the `role` of a top level section is
evaluated, so a child that sets a deviating one explicitly raises `SectionError` instead
of being quietly ignored. A child that sets none inherits the role of its subtree.

## Traits and the registry

The registry declares traits, validates values and decides the order they render in — it
never reaches into a prompt by itself:

```python
registry.defaults()          # declared defaults as a plain mapping
prompt.check(registry)       # values this prompt carries that the registry no longer admits
prompt.apply(patch, registry=registry)
```

`defaults()` hands the defaults over; it does not apply them. Filling missing traits in
during rendering would give a prompt behaviour that is not in its state — and setting such
a trait to `None` would no longer delete it but fall back to the default, a deletion that
silently does nothing. The layer above materialises defaults into the prompt once, so that
what takes effect is what the object says.

`check()` exists because a prompt outlives the specs it was built against: `apply()` only
validates incoming changes, so once a spec narrows its `choices`, older prompts keep values
no patch would admit today. It reports them and never raises.

## Rendering

The renderer configuration lives *inside* the prompt, so a stored variant is fully
described by the object alone:

```python
RendererConfig(
    format="keyvalue",                   # or "xml", "markdown"
    qualified_tags=True,                 # <behavior:character> instead of <character>
    constraints_first=True,              # traits before authored text
    developer_role="fold_into_system",   # or "native"
    trait_group_separator=" ",
    nested_headers=True,                 # keyvalue only, see below
)
```

`fold_into_system` is the default because LM Studio and Ollama fold developer messages
into the system message anyway when reached through their OpenAI-compatible endpoints.

**Trait routing.** The key names the target: `behavior.tone` renders into section
`behavior`. A trait without a dot, or one whose prefix names no enabled section, goes into
a general block at the start of the system message — never dropped, never raised over.

**Trait order.** Traits declared in the registry render in the order the registry declares
them, so related levers can be grouped instead of being left to the alphabet; everything
else follows its key. The prompt keeps its own traits sorted, so the order never depends on
how a prompt was assembled. Because that order is part of the output, it is also part of
`TraitRegistry.fingerprint()`.

**Formats differ on purpose.** `keyvalue` always prints the raw pair `GROUP name = value`
and ignores the `render` templates — that grammar is itself the signal. `xml` and
`markdown` use the template. Without one they fall back to the bare pair `name = value`,
because the tag or heading already carries the group; only a trait that ended up in the
general block keeps its full `GROUP name = value`, since there the group is the last thing
that still says where it belongs.

The address itself is the same in every format — `behavior.style.tone` renders as
`BEHAVIOR.STYLE tone = terse` and inside `<behavior:style>`, one prefix in two spellings.
Only the separator is format-specific.

**`nested_headers` decides how much address `keyvalue` carries.** On by default: every
section renders under its full key, so nesting becomes a longer address rather than an
indentation and the grammar stays flat.

```
#IDENTITY
IDENTITY tone = friendly

#IDENTITY.CHARACTER
You are Hera.

#IDENTITY.CREATOR
Made by Lukas.
```

A section that only groups others contributes no header of its own — its name says nothing
the children's keys do not already say.

Turn the option off and only top-level sections get a `#HEADER`; children then contribute
their text underneath, so `identity.character` and `identity.creator` arrive as two
adjacent paragraphs under `#IDENTITY`. That is the shape the reference example in
`docs/hera-prompts.md` shows, which is why the opt-out exists — but it is not the default, because it
makes `keyvalue` carry less than `xml` and `markdown`, and a comparison between the three
formats over a nested prompt would then measure address depth as much as format.

The option is a `keyvalue` matter. `xml` and `markdown` carry the address in their tags and
headings anyway and ignore it.

**Qualified tags are not well-formed XML.** A colon in a tag name is a namespace prefix and
would need an `xmlns:` declaration. Nothing here parses its own output, and the shape is
what the model reads, so `qualified_tags=True` stays the default. Render with
`qualified_tags=False` for anything that has to parse the result — it nests plain tag names
and goes through a parser unchanged.

**Budget.** Pass a `TokenBudget` and sections are dropped by ascending `priority` until
the rendering fits; `required=True` protects a section and its ancestors. If nothing
droppable is left, `BudgetExceeded` is raised.

The default counter estimates roughly three characters per token. That is a compromise, not
a measurement: underestimating lets the budget bite too late and the call runs into the
context limit, while overestimating drops one section too early, which is visible and
harmless. Pass a real tokenizer as `TokenBudget(counter=...)` — `apps/api` should do exactly
that — whenever the number has to be right.

**Why content is missing** is answered by three separate fields, because three separate
causes deserve three separate answers:

| field | cause |
| --- | --- |
| `snapshot.dropped_keys` | sections removed under budget pressure |
| `snapshot.unbound_slots` | slots that no binding filled |
| `unused_bindings` | bindings that matched no slot |

## Use inside an API

`PromptError` and its subclasses deliberately do **not** derive from `ValueError`.
Pydantic converts only `ValueError` and `AssertionError` raised inside validators into a
`ValidationError`, so a malformed prompt surfaces as `SectionError` or `TraitError` itself
instead of a wrapped validation error — which is what keeps these errors readable here.

The consequence sits one layer up: a FastAPI application that validates prompt JSON from a
request body receives a `PromptError`, not a `ValidationError`, and therefore answers
**500 instead of 422** unless it says otherwise. Register an exception handler there:

```python
@app.exception_handler(PromptError)
async def prompt_error_handler(request: Request, exc: PromptError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})
```

That belongs in the application, not in this library.

## What does **not** belong here

No prompt inheritance or overlays, no template engine, no variable interpolation inside
content, no caching, no tokenizer, no persistence, no history management, and no knowledge
of tools, memories, skills or chats. No provider specifics either beyond the three roles —
mapping `Message` onto a wire format is `hera_providers`' job.

The German specification this library was built against is kept verbatim as
`docs/hera-prompts.md`.
