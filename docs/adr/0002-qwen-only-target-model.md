# 2. Qwen3.6-35B is the only target model

- Status: accepted
- Date: 2026-08-26

## Context

The previous version targeted GPT-OSS-20B through LM Studio, and a surprising amount of the
codebase existed only to survive that choice:

- `normalize_harmony()` rewrote leaked `<|channel|>commentary…<|message|>` markup into call
  lines, mirrored by a second implementation in the browser.
- A text grammar — `EMOTION doubt(text="…")`, `NOTE write(...)`, `TRACE summary(...)`,
  `CALL websearch(...)` — replaced native function calling, because the model followed prose
  contracts more reliably than tool schemas. It came with a parser on the server and a second
  parser in `stream.js` that had to stay byte-compatible with it.
- A positional-argument fallback existed because small models drop keyword names.
- The prompt used a `keyvalue` grammar (`BEHAVIOR tone = terse`) because nesting confused
  3B-class models.

Every one of those is a permanent maintenance cost paid for one model's weaknesses.

## Decision

The only supported model is **Qwen3.6-35B** over an OpenAI-compatible endpoint, later
Qwen3.8-35B. The design may assume: native tool calling including parallel calls, a separate
reasoning channel, and reliable handling of XML-structured prompts.

Concretely: no harmony normalisation, no text call grammar, no second parser in the frontend, no
positional-argument fallback, and `RendererConfig(format="xml")` for prompt assembly.

Provider-specific handling is confined to `hera_providers`: `QwenAdapter` reads
`reasoning_content` when the server provides it and otherwise lifts `<think>…</think>` out of
the content stream. Everything above the provider sees one normalised event union.

## Consequences

- Running Hera against a weaker model will degrade — probably into ignored tool calls. That is
  accepted; supporting weak models is what produced the previous mess.
- Support for another model family is a new adapter inside `hera_providers` and nothing else.
  The boundary is the whole point.
- One known weakness of this model shapes a separate decision: it is unreliable at deciding for
  itself that a skill is relevant. See ADR 5.
