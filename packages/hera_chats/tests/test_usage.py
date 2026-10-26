"""What each turn cost, kept as a ledger and summed by day (#111, ADR 25)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session

from hera_chats import (
    Chat,
    CloseReason,
    MessageRepository,
    Tokens,
    TurnClosed,
    TurnUsage,
    UsageRepository,
    summarise,
    window_start,
)
from hera_providers import TextDelta, Usage

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def closed(prompt: int, completion: int, reason: CloseReason = "completed") -> TurnClosed:
    return TurnClosed(
        reason=reason,
        usage=Usage(
            prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion
        ),
    )


def row(at: datetime, prompt: int = 100, completion: int = 10) -> TurnUsage:
    return TurnUsage(
        owner_id=UUID(int=1),
        chat_id=UUID(int=2),
        message_id=UUID(int=3),
        at=at,
        prompt_tokens=prompt,
        completion_tokens=completion,
    )


class TestTheLedger:
    def test_a_closed_turn_is_one_row(self, session: Session, chat: Chat) -> None:
        messages = MessageRepository(session)
        message = messages.start_assistant_message(chat)
        written = UsageRepository(session).record(message, [TextDelta(text="hi"), closed(90, 9)])

        assert [(r.prompt_tokens, r.completion_tokens, r.ordinal) for r in written] == [(90, 9, 0)]
        assert written[0].chat_id == chat.id
        assert written[0].owner_id == chat.owner_id

    def test_a_resumed_turn_adds_its_own_part_and_does_not_count_the_first_twice(
        self, session: Session, chat: Chat
    ) -> None:
        """A turn that paused for a card is recorded again when it resumes, with the first
        part's `turn_closed` still in its events."""
        usage = UsageRepository(session)
        message = MessageRepository(session).start_assistant_message(chat)
        paused = [closed(100, 5, "awaiting_permission")]
        usage.record(message, paused)
        usage.record(message, [*paused, TextDelta(text="done"), closed(140, 20)])
        usage.record(message, [*paused, TextDelta(text="done"), closed(140, 20)])

        rows = usage.since(chat.owner_id, NOW - timedelta(days=3650))
        assert sorted((r.ordinal, r.prompt_tokens) for r in rows) == [(0, 100), (1, 140)]

    def test_a_turn_the_endpoint_reported_nothing_for_writes_nothing(
        self, session: Session, chat: Chat
    ) -> None:
        message = MessageRepository(session).start_assistant_message(chat)
        assert UsageRepository(session).record(message, [TurnClosed()]) == []

    def test_a_part_without_usage_keeps_its_place_in_the_order(
        self, session: Session, chat: Chat
    ) -> None:
        message = MessageRepository(session).start_assistant_message(chat)
        written = UsageRepository(session).record(
            message, [TurnClosed(reason="awaiting_answer"), closed(10, 1)]
        )
        assert [r.ordinal for r in written] == [1]

    def test_the_rows_outlive_the_messages(self, session: Session, chat: Chat) -> None:
        """Deleting a chat removes what was said, not what it cost."""
        messages = MessageRepository(session)
        message = messages.start_assistant_message(chat)
        UsageRepository(session).record(message, [closed(50, 5)])
        messages.delete_for_chat(chat.id)

        assert len(UsageRepository(session).since(chat.owner_id, NOW - timedelta(days=3650))) == 1

    def test_since_is_one_owners_and_starts_where_it_is_told(
        self, session: Session, chat: Chat, owner_id: UUID
    ) -> None:
        usage = UsageRepository(session)
        old = row(NOW - timedelta(days=40))
        new = row(NOW - timedelta(days=1))
        stranger = row(NOW)
        old.owner_id = new.owner_id = owner_id
        old.message_id, new.message_id, stranger.message_id = UUID(int=4), UUID(int=5), UUID(int=6)
        for item in (old, new, stranger):
            usage.add(item)

        found = usage.since(owner_id, NOW - timedelta(days=30))
        assert [r.message_id for r in found] == [UUID(int=5)]


class TestTheSummary:
    def test_every_day_has_a_slot_and_today_is_last(self) -> None:
        summary = summarise([], now=NOW, zone=ZoneInfo("UTC"), days=30)
        assert len(summary.days) == 30
        assert summary.days[-1].date == date(2026, 10, 26)
        assert summary.days[0].date == date(2026, 9, 27)
        assert all(day.tokens == Tokens() for day in summary.days)

    def test_a_day_is_the_readers_day(self) -> None:
        """23:30 UTC on the 25th is already the 26th in Berlin."""
        late = row(datetime(2026, 10, 25, 23, 30, tzinfo=UTC))
        utc = summarise([late], now=NOW, zone=ZoneInfo("UTC"), days=3)
        berlin = summarise([late], now=NOW, zone=ZoneInfo("Europe/Berlin"), days=3)

        assert [d.tokens.prompt_tokens for d in utc.days] == [0, 100, 0]
        assert [d.tokens.prompt_tokens for d in berlin.days] == [0, 0, 100]

    def test_the_totals_are_rolling_windows(self) -> None:
        rows = [
            row(NOW - timedelta(hours=2), 1, 1),
            row(NOW - timedelta(days=3), 10, 2),
            row(NOW - timedelta(days=20), 100, 3),
            row(NOW - timedelta(days=45), 1000, 4),
        ]
        summary = summarise(rows, now=NOW, zone=ZoneInfo("UTC"), days=30)

        assert summary.day == Tokens(1, 1)
        assert summary.week == Tokens(11, 3)
        assert summary.month == Tokens(111, 6)

    def test_a_short_chart_still_has_the_months_total(self) -> None:
        """The totals do not depend on how many bars were asked for."""
        rows = [row(NOW - timedelta(days=20))]
        summary = summarise(rows, now=NOW, zone=ZoneInfo("UTC"), days=7)

        assert sum(day.tokens.prompt_tokens for day in summary.days) == 0
        assert summary.month.prompt_tokens == 100

    def test_the_window_reaches_the_first_local_day_or_a_month_back(self) -> None:
        utc = ZoneInfo("UTC")
        assert window_start(now=NOW, zone=utc, days=7) == NOW - timedelta(days=30)
        assert window_start(now=NOW, zone=utc, days=60) == datetime(2026, 8, 28, tzinfo=utc)
