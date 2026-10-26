# 26. One question card may hold up to three questions

- Status: accepted
- Date: 2026-10-26

## Context

`hera__ask` used to take one `question`, and its description told her to "ask one question rather
than a list". Every question was a suspended turn: she asks, the turn closes, a person replies, and
the reply resumes the turn by sending the whole conversation again. So three things she needed to
know cost three cards, one after another, and three more round trips to the endpoint
([#64](https://github.com/VoidEUW/hera/issues/64)).

The rule had a reason, and it still holds for some questions: when an answer decides whether the
next question makes sense, the next question should not be asked yet. It does not hold for
questions that are independent of each other, such as *which deck?* and *keep the speaker notes?*.

Many of those questions are also a pick between a few things she already has in mind. Typing
"the 2024 one" to answer a question that could have offered "2024" and "2025" is work she can save
the person.

## Decision

**One `hera__ask` call takes `questions`: one to three of them, each with optional `options`, two
to four short choices.**

- **One card, one Reply.** The questions are one call, so they get one result and one card, with a
  field per question. One card per question would give a single call three things to settle.
- **The description says when to bundle.** Put every question into one call, and do not call twice
  in a row. Bundle only independent questions; if one answer changes whether the next makes sense,
  ask that one alone.
- **Options are a shortcut, not a fence.** The choices are chips above the field. Picking one is the
  answer, and typing replaces the pick. A person who means neither choice still says so.
- **`kind` stays once per call** (ADR 17). The card has one tone. One per question would be more
  precise, but it is more schema for the target models to fill in, and almost every bundle has one
  occasion.
- **The schema is written inline.** The SDK puts a nested type behind `$ref` into `$defs`. The
  schema is prompt text, and the smaller models ADR 19 targets do not reliably follow a pointer to
  learn what one question looks like.
- **The reply quotes the questions.** One question is answered by its reply alone, as before.
  Several come back numbered, each answer beside its question
  (`1. Which deck? → 2024`). Otherwise a model reading bare lines has to match them to its call by
  position, and that is the bookkeeping it gets wrong.
- **Nothing validates the arguments, so they are read tolerantly.** The call is never dispatched,
  so the published schema is a request the model may not have honoured. `hera_chats` reads:
  - a list of objects;
  - a list of bare strings;
  - the old single `question`, from a model that read an older catalogue.

  It drops an `options` list left with fewer than two choices, and caps nothing: the limits are
  the schema's, and `hera_chats` may not learn them.

## Consequences

- `AnswerRequired.question` became `questions` (each a `Question` with `text` and `options`), and
  `AnswerGiven.text` became `answers`. Turns persisted in the old shape are folded into the new one
  when they are read, so the API, the export and the browser only know the new shape.
- `POST /chats/{id}/answers` takes `answers`, one per question, and refuses a count that does not
  match with 422. Padding a short list would put a reply beside the wrong question.
- Three is a ceiling she can reach. A card with three fields is still one glance, and a fourth would
  make it a form.
