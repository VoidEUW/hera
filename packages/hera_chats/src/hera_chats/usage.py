"""What the turns cost, by day and over the last day, week and month (#111).

Counts come from the endpoint's own report (``TurnClosed.usage``) and nowhere else: Hera does
not tokenise anything to estimate them, so a server that reports nothing counts as nothing.

Days are the reader's days. The rows are stored in UTC and bucketed here in the time zone the
caller names, because "yesterday" is a fact about where a person is, not about the server. The
three totals are rolling windows instead — the last 24 hours is the same span wherever you are.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from hera_chats.models import TurnUsage

__all__ = ["DayUsage", "Tokens", "UsageSummary", "summarise", "window_start"]

MONTH = timedelta(days=30)
"""The longest of the three totals, and so the oldest row a summary ever needs."""


@dataclass(frozen=True)
class Tokens:
    """A prompt count and a completion count, added together from any number of turns."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: Tokens) -> Tokens:
        return Tokens(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )


@dataclass(frozen=True)
class DayUsage:
    """One calendar day in the reader's time zone."""

    date: date
    tokens: Tokens = field(default_factory=Tokens)


@dataclass(frozen=True)
class UsageSummary:
    """A bar per day, oldest first and ending today, and the three rolling totals."""

    days: list[DayUsage]
    day: Tokens
    week: Tokens
    month: Tokens


def window_start(*, now: datetime, zone: ZoneInfo, days: int) -> datetime:
    """The oldest moment a summary of ``days`` days reads: the start of its first local day,
    or thirty days back for the month's total, whichever is earlier."""
    today = now.astimezone(zone).date()
    first = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=zone)
    return min(first, now - MONTH)


def summarise(
    rows: Sequence[TurnUsage], *, now: datetime, zone: ZoneInfo, days: int
) -> UsageSummary:
    """Bucket ``rows`` into the last ``days`` local days, and total the rolling windows.

    Every day is present, a quiet one as zero, so the chart has a slot for it.
    """
    today = now.astimezone(zone).date()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    by_day: dict[date, Tokens] = dict.fromkeys(dates, Tokens())
    day = week = month = Tokens()

    for row in rows:
        spent = Tokens(row.prompt_tokens, row.completion_tokens)
        local = row.at.astimezone(zone).date()
        if local in by_day:
            by_day[local] += spent
        age = now - row.at
        if age <= MONTH:
            month += spent
            if age <= timedelta(days=7):
                week += spent
                if age <= timedelta(days=1):
                    day += spent

    return UsageSummary(
        days=[DayUsage(date=when, tokens=by_day[when]) for when in dates],
        day=day,
        week=week,
        month=month,
    )
