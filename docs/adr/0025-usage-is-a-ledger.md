# 25. What a turn cost is kept in a ledger, not read back out of the messages

- Status: accepted
- Date: 2026-10-26

## Context

Settings → Usage ([#111](https://github.com/VoidEUW/hera/issues/111)) shows tokens per day for the
last thirty days, and totals for the last 24 hours, 7 days and 30 days. Every closed turn already
records what the endpoint reported, as `TurnClosed.usage` inside the message's event list, so the
first idea was to read the numbers back out of `chat_messages.events` at query time.

That would answer the wrong question. Messages do not stay: deleting a chat removes its messages
(`delete_for_chat`), and asking a question again, reworded or not, removes the answer it replaces
(`truncate_from`). Read from the messages, last Tuesday's bar would shrink when a chat from last
Tuesday was deleted. It would show what is left, not what was spent, and a person comparing two
weeks could not tell which had happened.

A message can also carry more than one `turn_closed`. A turn that paused for a permission card or
a question keeps the first part's close when it resumes, and each close counts only its own part.

## Decision

**Each closed turn's usage is written once to `chat_usage`, beside the message, and nothing
deletes it.**

- One row per `turn_closed` that reported usage: owner, bare chat and message ids, its position
  among the message's closes (`ordinal`), when it closed (`at`), and the prompt and completion
  counts. `(message_id, ordinal)` is unique. Recording a resumed message again adds the new part
  and leaves the earlier one alone.
- It is written in the same unit of work that records the message (`hera_core.api.chats._record`),
  next to the skill-usage count, through `hera_chats.UsageRepository`.
- Migration 0006 backfills it from the `turn_closed` events of the messages that still exist, dated
  by when each message was last written.
- `GET /usage?days=30&tz=` cuts the rows into days in the reader's time zone (the browser sends its
  own, then the one on Settings → General, then UTC). The three totals are rolling windows. Counts
  are only what the endpoint reported: Hera does not estimate, so an endpoint that reports nothing
  counts as nothing.

## Consequences

- Deleting a chat keeps its usage rows. They hold counts and ids, nothing anybody said, so keeping
  them keeps no content; the chat id points at nothing once the chat is gone.
- A cancelled turn never closes, so whatever it used before it stopped is not counted. The
  endpoint usually reports usage only at the end of a stream, so there is nothing to count anyway.
- Usage from before the ledger existed is only as complete as the messages that survived until
  the upgrade.
- A per-model or per-chat breakdown later is a `GROUP BY` on this table, not a new scan of every
  message's JSON.
