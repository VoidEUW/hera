"""What time it is, as the model reads it.

**A model that does not know the date guesses the year.** Asked what is current it answers from
its training data, confidently and a year late, and the person has no way to tell that from an
answer that is merely wrong. `hera__search` already says to use it "whenever the answer depends
on what is true now rather than on what you were trained on" — this is what makes that sentence
actionable, because *now* was the one thing she could not establish.

**Implicit rather than a tool.** A `what_time_is_it` tool would cost a round trip to learn
something that is free, and would only be called by a model that already suspected it needed to
— which is exactly the model that does not have the problem. It is thirty tokens in the prompt.

**UTC leads, local follows.** UTC is unambiguous and is what a search result's timestamp should
be reasoned against; local time is what the person means by "tomorrow". Both, labelled, because
picking one makes half the questions harder.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FORMAT = "%A %d %B %Y, %H:%M"
"""Written out rather than ISO. ``2026-08-28T12:07Z`` is a string a model has to parse before
it can reason about it, and the weekday — which it cannot derive reliably — is free here."""


def render(timezone: str = "", *, now: datetime | None = None) -> str:
    """The line bound into the ``now`` slot.

    ``timezone`` is an IANA name from ``config.toml``. Empty means UTC only, which is the
    honest default for a deployment nobody has told where it is — better than guessing from the
    server's clock, since the machine's zone and the person's are different questions and a
    self-hosted Hera may well be on a box in another country.

    An unusable name degrades to UTC rather than raising. This runs on every turn, and a typo in
    a settings file is not a reason to stop answering; the person sees UTC and can tell.
    """
    moment = now if now is not None else datetime.now(UTC)
    line = f"The current date and time is {moment.astimezone(UTC).strftime(FORMAT)} UTC."

    local = _local(moment, timezone)
    if local is None:
        return line
    return f"{line} Where the person is, it is {local.strftime(FORMAT)} ({timezone})."


def _local(moment: datetime, timezone: str) -> datetime | None:
    """The same moment in the person's zone, or ``None`` if there is not a usable one.

    ``None`` covers three cases that are one case to the caller: no zone configured, a name
    ``zoneinfo`` does not know, and a system with no tz database at all. All three mean "say UTC
    and nothing else", and telling them apart in the prompt would be describing a configuration
    problem to a model that cannot fix it.
    """
    if not timezone or timezone.upper() == "UTC":
        return None
    try:
        return moment.astimezone(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None


def is_known(timezone: str) -> bool:
    """Whether ``zoneinfo`` can resolve this name. Used to refuse a bad one on the way in.

    Refused at the API rather than silently degraded, unlike :func:`render`: a person typing a
    zone into a settings screen should be told it is wrong *then*, while a turn that has already
    started should not fail over a value somebody edited into a file last week.
    """
    if not timezone:
        return True
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False
    return True
