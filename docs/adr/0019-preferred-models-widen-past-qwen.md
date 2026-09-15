# 19. Preferred models widen past Qwen, and a model may decline tool calling

- Status: accepted
- Date: 2026-09-15

> This narrows [ADR 2](0002-qwen-only-target-model.md)'s target-model list and nothing else. Its
> architecture bet — native tool calling assumed, XML-structured prompts, no second parser —
> stays binding, reaffirmed below rather than reopened. It also does not reopen
> [ADR 18](0018-a-model-may-carry-request-options.md)'s refusal to attach behaviour to a model
> classification; see Alternatives considered.

## Context

ADR 2 named one model, Qwen3.6-35B, and forbade guessing at another's behaviour, because
accommodating a menagerie of weak models is what the previous version's parsers and fallbacks
were for. That bet had already been quietly outgrown in practice: `docs/status.md` records
issue #63 checked against Qwen3.6, DeepSeek and GLM5.3 as well, and
[ADR 18](0018-a-model-may-carry-request-options.md) exists because a real deployment ran GLM-4.7
and gpt-oss and needed a place to put their request quirks. `QwenAdapter` — the one
`StreamAdapter` implementation `hera_providers` has — was already written to degrade gracefully
for a model with no reasoning channel at all, and its own docstring names Gemma by name for a
template quirk it already handles. The single-model fiction was costing accuracy without buying
the discipline it was meant to.

The concrete incident that forced the question: a chat running Gemma (configured as the active
model on a local LM Studio endpoint, chosen because Qwen3.6-35B does not fit the machine) was
asked to publish an SVG artifact. Gemma knew the tool existed — its definition travels in every
request's `tools` field regardless of what the model does with it — but instead of a native
`tool_calls` delta it free-generated prose that *looked* like a call, in two different invented
syntaxes across two attempts. Nothing was wrong with Hera's parsing, because there was nothing to
parse: the model never called a tool, it wrote about one. ADR 2 already named this outcome and
accepted it — *"Running Hera against a weaker model will degrade — probably into ignored tool
calls."* — but gave nobody a way to make the degradation clean instead of a broken artifact card
on screen.

## Decision

**The preferred model families are DeepSeek, GLM, Qwen, Kimi, Gemma, Anthropic and OpenAI.**
"Preferred" means the prompt is written in XML-tagged prose (`RendererConfig(format="xml")`),
which every one of these families reads as ordinary structured text — nothing in `hera_prompts`
is Qwen-specific, it never was. It does **not** mean each is reached through its own wire
protocol: Anthropic and OpenAI here mean *reachable through an OpenAI-compatible endpoint* — a
gateway, a router, or (for OpenAI) its own API, which already speaks the shape `hera_providers`
sends. Anthropic's native Messages API is a different wire format entirely (`/v1/messages`,
`x-api-key`, content-block tool use) and is explicitly **not** supported by this record — that
would be a new `StreamAdapter`, per ADR 2's own extension mechanism, and nobody has asked for it
yet.

`QwenAdapter` keeps its name. It already handles a model with no reasoning channel, no `<think>`
tags, and a well-formed-but-empty `<think>\n\n</think>` (the Gemma case its own docstring names)
as a no-op — nothing about widening the family list requires new adapter code. A rename is left
for whenever it stops being confusing, not blocked on this record.

**A registered model may say it does not call tools reliably.** `ModelEntry.tool_calling: bool =
True` is a new field, set by a person on Settings → Models, never inferred from a model's id or
name string — the same stance ADR 18 already took about `glm-4.7-flash` vs.
`GLM-4.7-Flash-Q4_K_M` vs. `zai/glm-4.7` being three names for one thing. `False` does exactly one
thing: `Turn._tool_specs()` returns `([], "")` for that model unconditionally, the same values it
already returns when no registry is configured at all. The model is never offered a tool, and the
prompt never mentions that tools exist — both halves of the existing "say nothing rather than
announce an empty catalogue" rule, extended to cover "say nothing because this model cannot use
what it would be offered."

This is not a parser. Nothing reads a garbled call back out of `content` and nothing tries to
recover what the model meant — the two-shapes-in-two-tries incident above stays exactly as broken
as it was, right up until a person flips the switch, after which it simply never happens again
because there is nothing left to attempt. That is the whole mechanism.

## Consequences

**Turning `tool_calling` off costs everything, not just artifacts.** Skills, memory writes,
scratch files, artifacts — all of it goes through the one tool catalogue `_tool_specs()` serves,
so a model flagged this way answers in prose alone. That is the honest trade, not a partial one,
and it is why the field defaults to `True`: most configured models should keep full capability,
and the flag exists for the ones that provably cannot use it anyway.

**Nobody is warned automatically.** A person notices unreliable tool-calling by watching it
happen, the way this record's own incident was noticed, and then sets the flag by hand. Detecting
it automatically — a heuristic over finish reasons, or repeated ignored-tool-offer turns — is
future work this record does not attempt, for the same reason ADR 18 kept its preset list to two:
a wrong guess here is a capability silently switched off under a model that could have used it.

**The endpoint documentation now names seven families instead of one.** `README.md`,
`docs/website/configuration.md`, `quick-start.md`, `source-installation.md` and
`docker-installation.md` say so, with the same "any endpoint with working native tool calling"
caveat they already carried — it now has a name for what to do when that caveat is not met.

## Alternatives considered

**Match the model id and decide for it.** Rejected for the reason ADR 18 already gave about
`chat_template_kwargs`: a person's typed model name is not a reliable classifier, and a wrong
guess here means a model that *can* call tools has them silently withheld, which is a worse
failure than the one this record fixes because nothing on screen says why.

**A `ModelKind` capability enum.** This is the exact shape
[ADR 18](0018-a-model-may-carry-request-options.md) already refused — *"once the system knows
what a model is, the next request is for it to adjust the prompt, then the parser."*
`tool_calling` is one bit with one fixed effect, set by a person for the one model they
configured, not a classification anything else reads.

**Recover the failed call from its prose.** This is ADR 2's forbidden second parser, and the two
different invented syntaxes across two attempts in this record's own incident are exactly why:
there is no bounded grammar to write a parser against, a model free-generating its best guess at
a call can invent a new one every time.
