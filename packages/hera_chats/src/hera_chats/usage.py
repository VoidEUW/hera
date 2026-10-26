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

__all__ = ["DayUsage", "Tokens", "Totals", "UsageSummary", "summarise", "window_start"]

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
class Totals:
    """One window's tokens, and what the endpoint and Hera's own clock said about them.

    Every rate is over the rows that *have* the number, and ``None`` when none do. An endpoint
    that never reports its cache is not one with a 0% cache rate, and a turn that was never
    timed is not one that took no time — averaging either in would put a figure on the screen
    that nobody measured.
    """

    tokens: Tokens = field(default_factory=Tokens)
    reasoning_tokens: int | None = None

    cached_tokens: int = 0
    cache_prompt_tokens: int = 0
    """Prompt tokens of the rows that reported their cache: the denominator of the rate."""

    timed_completion_tokens: int = 0
    generating_ms: float = 0.0
    first_token_ms_sum: float = 0.0
    first_token_count: int = 0

    def add(self, row: TurnUsage) -> Totals:
        cached = row.cached_tokens is not None
        timed = row.generating_ms and row.timed_completion_tokens
        first = row.source == "turn" and row.first_token_ms is not None
        return Totals(
            tokens=self.tokens + Tokens(row.prompt_tokens, row.completion_tokens),
            reasoning_tokens=(
                self.reasoning_tokens
                if row.reasoning_tokens is None
                else (self.reasoning_tokens or 0) + row.reasoning_tokens
            ),
            cached_tokens=self.cached_tokens + (row.cached_tokens or 0),
            cache_prompt_tokens=self.cache_prompt_tokens + (row.prompt_tokens if cached else 0),
            timed_completion_tokens=self.timed_completion_tokens
            + ((row.timed_completion_tokens or 0) if timed else 0),
            generating_ms=self.generating_ms + ((row.generating_ms or 0.0) if timed else 0.0),
            first_token_ms_sum=self.first_token_ms_sum
            + ((row.first_token_ms or 0.0) if first else 0.0),
            first_token_count=self.first_token_count + (1 if first else 0),
        )

    @property
    def cache_rate(self) -> float | None:
        """Share of the prompt the server had cached, from nought to one."""
        if not self.cache_prompt_tokens:
            return None
        return self.cached_tokens / self.cache_prompt_tokens

    @property
    def tokens_per_second(self) -> float | None:
        """Completion tokens over the time spent writing them."""
        if not self.generating_ms:
            return None
        return self.timed_completion_tokens / (self.generating_ms / 1000)

    @property
    def first_token_ms(self) -> float | None:
        """How long, on average, a turn took to show anything."""
        if not self.first_token_count:
            return None
        return self.first_token_ms_sum / self.first_token_count


@dataclass(frozen=True)
class DayUsage:
    """One calendar day in the reader's time zone."""

    date: date
    tokens: Tokens = field(default_factory=Tokens)


@dataclass(frozen=True)
class UsageSummary:
    """A bar per day, oldest first and ending today, and the three rolling totals."""

    days: list[DayUsage]
    day: Totals
    week: Totals
    month: Totals


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
    day = week = month = Totals()

    for row in rows:
        local = row.at.astimezone(zone).date()
        if local in by_day:
            by_day[local] += Tokens(row.prompt_tokens, row.completion_tokens)
        age = now - row.at
        if age <= MONTH:
            month = month.add(row)
            if age <= timedelta(days=7):
                week = week.add(row)
                if age <= timedelta(days=1):
                    day = day.add(row)

    return UsageSummary(
        days=[DayUsage(date=when, tokens=by_day[when]) for when in dates],
        day=day,
        week=week,
        month=month,
    )
