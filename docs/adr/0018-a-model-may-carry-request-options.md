# 18. A model may carry request options, and Hera does not know what they mean

- Status: accepted
- Date: 2026-09-10

> This does **not** reopen [ADR 2](0002-qwen-only-target-model.md). ADR 2 is about what the
> prompt is written for and about refusing to parse a second model's output. Nothing here parses
> anything.

## Context

[Issue #63](https://github.com/VoidEUW/hera/issues/63) began as *GLM-4.7-Flash loses the
conversation from turn two*. Most of it turned out to be two duplication bugs in the turn loop,
which are fixed and are not what this record is about. What survived after those were fixed is a
real and separate need.

GLM-4.7 does not keep the reasoning of earlier turns when it renders a conversation unless it is
told `chat_template_kwargs.clear_thinking = false`. gpt-oss takes a `reasoning_effort`. Neither is
a field the OpenAI chat-completions protocol has; both are fields their servers accept, and there
was nowhere in Hera to put one.

The tempting answers are both wrong:

**Name the fields.** A `clear_thinking: bool` on `ChatRequest` would put one server's chat
template into the vocabulary four packages share, and the next such flag would be the fifth. This
is precisely what `ChatRequest.extra` was already written to prevent — its docstring says so:
*"Guessing at those fields here would put provider specifics in the shared vocabulary, which is
the thing this package exists to prevent."* The seam existed and nothing filled it.

**Detect the model.** Match `glm` in the model id and send the flag. But `glm-4.7-flash`,
`GLM-4.7-Flash-Q4_K_M` and `zai/glm-4.7` are the same weights under three names a person typed,
and getting it wrong means silently sending a field that makes a *different* server reject the
whole request. It is the same argument `ProviderKind` already settled about guessing an endpoint's
identity from its `base_url`, and it should be settled the same way.

## Decision

**A registered model carries `options`: request-body fields Hera passes through and does not
read.** They live on `ModelEntry` in `config.toml`, travel as `ChatsSettings.extra`, and are
merged into the body last by `hera_providers.chat_payload` through `ChatRequest.extra`.

**Per model, not per endpoint.** The same OpenRouter URL serves GLM-4.7 and GLM5.3 and only one
wants the flag, so the endpoint is the wrong grain. They travel with `model` everywhere the model
travels — `use_provider` takes both, because *which model is active* is one decision and carrying
the previous model's flags to the next one is the bug this grain exists to prevent.

**Known ones are offered, never matched.** `hera_core.model_presets` holds two — GLM-4.7 and
gpt-oss — served to the Models screen as a picker. A preset *fills the editor* and nothing records
which one was used, so a later version of Hera changing a preset cannot change a setting under an
install that already chose it.

**One rule about content, and it is not a schema.** Options may not set `model`, `messages`,
`stream`, `stream_options`, `tools` or `tool_choice`. Because the merge is last, `{"messages": []}`
would replace the conversation with nothing — and the symptom would be a model that has forgotten
everything, which is indistinguishable from the bug this field was added to fix. Refused with a
422 rather than dropped: a setting that is silently ignored is worse than one that says no.

## Consequences

**Hera cannot tell you whether an option worked.** It is opaque by construction, so a typo in a
key is a field the server ignores, and a wrong value is a 400 from somebody else's API surfaced as
a failed turn. This is the price of not having a schema, and it is the right price — the
alternative is a schema that is wrong about every server it was not written against.

**The field is a place a prompt could hide.** Someone could put a system message in it. The size
cap is what keeps that from being convenient rather than what makes it impossible; the honest
guard is that `~/.hera/config.toml` is a file a person reads.

**Two presets is not a catalogue.** This list is not meant to grow into a directory of every
OpenAI-compatible server's flags. Anything not in it is typed into the same field by hand, which
is the supported path and always was.

## Alternatives considered

**Per-endpoint options on `ProviderEntry`.** Simpler, one fewer level — and wrong for the case
that earned this, which is two models on one URL wanting different things.

**A `ModelKind` enum beside `ProviderKind`, with behaviour attached.** This is the shape that
turns into provider-specific normalisation a version at a time: once the system knows *what a
model is*, the next request is for it to adjust the prompt, then the parser. ADR 2 exists to keep
that door shut. A bag of fields nobody interprets keeps it shut.
