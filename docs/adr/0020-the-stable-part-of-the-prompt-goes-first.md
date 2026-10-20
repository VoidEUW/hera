# 20 — The stable part of the prompt goes first, and what changes goes last

- Status: accepted
- Date: 2026-10-04
- Relates to: [#144](https://github.com/VoidEUW/hera/issues/144)

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

### What this cost the skills, and what was done about it

The skills were **not** merely relocated. In the frame they were a section of configuration, read
with the rest of the prompt; after the history they are text inside a user-role message, which is
to say text the model may reasonably take for something the person typed. `_you asked for it by
name_` is a weak signal against a hundred tokens of somebody's instructions.

The two ways to restore the standing were both rejected on evidence rather than taste:

- **A `system` message after the history.** Not something strict templates accept, and the ones that
  refuse are the same family that answers an *empty message* on adjacent roles — so this would trade
  one blank answer for another.
- **A `developer` message.** The role exists (`hera_prompts` can emit it) but is not portable: whether
  a server honours it or folds it into the system prompt is, per its own docstring, "the server's
  business", and the compiler's default is to fold it *before* the request rather than risk it.

So the boundary is **stated in the text** instead: the skill block is introduced as instructions
standing behind the request and explicitly not something the person said, and it is told to say
plainly if it conflicts with what was actually asked. That last clause matters — a skill that is
wrong should produce a disagreement rather than a silent substitution, and only a note that claims
no authority over the request can ask for one honestly.

This is a partial repair and is recorded as one. It does not make a skill as strong as a system
section, and nothing here claims it does; the tests pin both halves — that the boundary text is
present, and that no `system` or `developer` message carries the body, so re-adding the skills slot
to the frame cannot pass unnoticed as a pure cache win.

**All three notes are merged into one user message, not three.** They are all user-role, and a
strict template answers an empty message when roles do not alternate, so a turn with a clock, a
browser failure and a selected skill produced four consecutive user messages and a supported target
returned nothing. One message, notes first and the question last, keeps the cache win — the notes
still follow the history — and keeps the roles alternating.

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

## Measured

`docs/status.md` asks for numbers rather than intentions, so here they are.

Two things had to be got right for any of them to mean anything, and both were wrong first:

- **The instrument was validated before it was trusted.** An identical request must come back ~99.9%
  cached before any figure about a *changing* prompt is read, which proves the metric responds to
  content rather than reporting a warm slot. The floor is reported with every table here.
- **Each arrangement warms its own cache immediately before its two measured sends.** Without that, an
  arm is measured against a slot its own earlier sends have warmed. This is not hypothetical: it
  produced a "before" figure of 99.9% cached once, and an "after" figure of 20.4% another time, both
  published here before being caught.

## Measured, properly

The comparison this ADR exists for was finally made by running the **real turn on both
arrangements** — the "before" being the commit where `now`, `problems` and `skills` are all bound
into the system frame, checked out and run rather than imitated. A `Turn` is built by the real
orchestrator, `FakeProvider` captures what it actually sent, and that request is replayed at the
endpoint. MiniCPM5-2B Q8_0, `-ngl 99`, `-ctk/-ctv q8_0 -c 16384`. Two sends identical, then two a
minute apart; the clock is the only difference.

| exchanges in history | before | after |
|---|---|---|
| 1 | 90.7% | 90.1% |
| 3 | 86.5% | 90.5% |
| 6 | 81.4% | 91.1% |
| 12 | **72.1%** | **92.1%** |
| identical request (the floor, both) | 99.9% | 99.9% |

**Before, the cache degrades as the conversation grows. After, it does not.** That is the whole claim,
and the *shape* of the two columns is the evidence rather than any single figure. Twenty points at
twelve exchanges, and none of it at one.

**There is no benefit in a short conversation, and that is worth saying rather than hiding in the
table.** At one exchange the before arrangement is marginally *ahead* (90.7% against 90.1%), which is
what a first measurement showed and nearly sent me hunting for a regression: 88.6% against 90.3%,
which looked like noise and was. The reason is visible in the render — with almost no history the
clock sat at 94.8% of the prompt, so "ahead of the conversation" and "near the end of the frame" were
nearly the same place. The fix is worth what the thing it protects is worth, and a short chat has
almost nothing to protect.

**An earlier version of this section carried a table claiming 4.0% → 98.4% on the 2B and 0.0% →
20.4% on the 9B, and a later one replaced it with 47.1% against 90.1%. Both are struck out.** The
20.4% came with an explanation — "the same effect on a shorter prompt" — that was arithmetically
impossible: a 646-token prompt losing a ~60-token tail should cache about 91%. Neither set was
measured with the variable that decides the question.

Both mistakes are the same one, and it is not an obvious one: **measuring the mechanism on the case
where it has nothing to do.** The 47%/90% pair and the 88.6%/90.3% pair are both *true* measurements
of a prompt with almost no conversation in it, and both say nothing about this decision, because how
much text sits behind the volatile slot is the entire variable and neither varied it.

### What this does not show

One model, one context size, one kind of conversation. MiMo-9B was not re-measured on both
arrangements, so no cross-model claim is made here. And the gain is in cache *reuse*, not latency or
cost as such — a 2B on this card re-reads 200 tokens quickly enough that the saving is invisible
unless you count it. The honest description is that this grows with the conversation, not that it is
large.

## Enforced by

`packages/hera_chats/tests/test_prompt_cache.py` asserts, on what the provider was actually sent,
that the clock and the skill body are absent from the frame, that the frame is byte-identical
across a minute and across a skill selection, and that both still reach the model. Six of those
assertions fail against the previous arrangement.
