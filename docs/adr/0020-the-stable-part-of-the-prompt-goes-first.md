# 20 — The stable part of the prompt goes first, and what changes goes last

- **Status:** accepted
- **Date:** 2026-10-04
- **Relates to:** [#144](https://github.com/VoidEUW/hera/issues/144)

## Context

A turn's request is the system frame, then the history, then the question. Inference servers cache
that request by prefix: everything up to the first changed token is reused, and everything from
there on is re-read. It is the largest cost in a conversation that is mostly recall, because the
history is where the tokens are.

The frame is built from a tree in `hera_profiles/builder.py`, ordered by a `priority` that means
*"how rarely does this change"*. By that rule the volatile things were already late: the clock was
priority 68 of 70, and the router's skill choice 60. That ordering is correct and it was still
wrong, because **the frame is followed by the entire conversation**. Late in the frame is nowhere
near late enough. Anything that changes per turn re-reads all of the history behind it.

Two slots were volatile:

- **`now`**, rendered at minute granularity (`clock.py`, `%H:%M`), so it changed on most turns.
- **`skills`**, the router's choice, which changes whenever routing lands differently.

Meanwhile the static half of the frame — safety, identity, approach, the tool catalogue — hit the
cache every time. The cache was being spent on the cheap half and thrown away on the half that
grows.

## Decision

**A slot whose text can differ between two turns does not go in the frame.** It goes after the
history, as a user-role message, in this order: clock, then skills, then the question.

`_wrap_up` already reasoned about this for the final round: a note that is true of *this moment*
rather than of this deployment belongs in a user-role message, because a system prompt that changed
shape would be a second prompt to reason about. That reasoning generalises, and the two volatile
slots now use it.

The order is deliberate. A skill's instructions belong next to the thing being asked, and a note
*after* the question reads as part of it.

`project` stays in the frame: it is empty unless the chat belongs to a project, so it is already
absent for most turns and is not a per-turn cost.

## What this costs

Nothing in what the model reads. The same text is sent, in the same relative order to the question,
as two user-role messages rather than one system section. A model that was told the time in the
system prompt is now told it one message later, and a selected skill one later still — both still
before the question.

What is given up is a small recency effect: text in the system prompt is arguably more
authoritative than text in a user message. That was already conceded for `_wrap_up`, and the clock
and a skill's body are instructions about *this moment*, which is what a user-role message is for.

## What this does not do

It does not make the prompt smaller. Measured, the default frame is about 3,500 characters of mind
regions and 5,300 of tool descriptions — roughly 2,200 tokens — and nothing here removes any of it.
Shortening that text is a separate piece of work, and it is not obvious that it is worth doing:
#143 found 165 tool calls from a real model with none malformed, so "shorter descriptions raise the
tool-call rate" is a hypothesis, not a finding. Measure before rewriting prose.

## Enforced by

`packages/hera_chats/tests/test_prompt_cache.py` asserts, on what the provider was actually sent,
that the clock and the skill body are absent from the frame, that the frame is byte-identical
across a minute and across a skill selection, and that both still reach the model. Six of those
assertions fail against the previous arrangement.
