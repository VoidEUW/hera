"""The prompt frame must not change because the clock did.

A KV cache is a prefix cache. Everything up to the first changed token is reused, and everything
from there on is re-read. So the question this file answers is not "is the timestamp right" but
"does the timestamp sit in front of the conversation".

It used to. `context.now` was priority 68 in `hera_profiles/builder.py` -- second from last in the
frame -- and the whole history follows the frame. Rendered at minute granularity, every tick of the
minute therefore invalidated the whole conversation behind her, while the static half of the frame
(safety, identity, approach, the tool catalogue) kept hitting the cache. The cache was spent on the
cheap half and thrown away on the half that grows.

The fix is placement, not granularity: the clock is bound after the history as a user-role note,
which is the same reasoning `_wrap_up` already gives for the final round -- it is true of *this
moment* and not of this deployment.

Asserted through what the provider was actually sent, rather than through a helper, because the
whole claim is about the shape of the request on the wire.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import pytest
from chat_support import drain

from hera_chats import TurnContext
from hera_providers import ChatMessage, Role


def sent(provider: Any) -> list[Any]:
    """The requests a provider was asked, oldest first."""
    return list(provider.requests)


def texts(request: Any) -> list[str]:
    return [(m.content or "") for m in request.messages]


async def run(make_orchestrator: Any, **context: Any) -> list[Any]:
    """Run one whole turn and hand back what it asked the provider."""
    from hera_providers import FakeProvider, text_turn

    provider = FakeProvider([text_turn("ok")])
    turn = make_orchestrator(provider).begin(TurnContext(**{"text": "hi", **context}))
    await drain(turn.stream())
    return sent(provider)


def split_frame(request: Any) -> tuple[list[str], list[str]]:
    """Where the request stops being the frame and becomes the conversation.

    Located by the first user message, because that is the boundary that decides what the cache
    keeps: the frame before it is reused, everything from it on is re-read.
    """
    contents = texts(request)
    for index, message in enumerate(request.messages):
        if message.role is Role.USER and contents[index]:
            return contents[:index], contents[index:]
    raise AssertionError(f"no user message in {[m.role.value for m in request.messages]}")


async def test_a_minute_apart_sends_the_same_frame(make_orchestrator: Any) -> None:
    """The claim, directly: nothing before the conversation moved."""
    early = await run(make_orchestrator, now="Friday 03 October 2026, 14:04")
    later = await run(make_orchestrator, now="Friday 03 October 2026, 14:05")

    early_frame, _ = split_frame(early[0])
    later_frame, _ = split_frame(later[0])

    assert early_frame, "the frame should not be empty"
    assert early_frame == later_frame, "a minute changed the frame, so the prefix cache is lost"


@pytest.mark.parametrize("minute", ["00", "30", "59"])
async def test_no_system_message_carries_the_date(make_orchestrator: Any, minute: str) -> None:
    """The frame is entirely system messages, so this is the same claim stated directly."""
    asked = await run(make_orchestrator, now=f"Friday 03 October 2026, {minute}")

    frame, _ = split_frame(asked[0])
    offenders = [c for c in frame if "October 2026" in c]

    assert not offenders, offenders


async def test_the_clock_reaches_the_model(make_orchestrator: Any) -> None:
    """Placement is not a demotion: she still has to be told the time."""
    asked = await run(make_orchestrator, now="Friday 03 October 2026, 14:05")

    _, rest = split_frame(asked[0])

    assert any("14:05" in c for c in rest), rest


async def test_the_clock_sits_after_the_history_and_before_the_question(
    make_orchestrator: Any,
) -> None:
    """The exact position: conversation, then the notes, then the question within them.

    The clock sits between the history and the question rather than after both, because a note
    that follows the question reads as part of it. The clock and the question now share one
    message -- role alternation requires it -- so the ordering is *within* that message and is
    checked as text.
    """
    asked = await run(
        make_orchestrator,
        history=(
            ChatMessage(role=Role.USER, content="earlier question"),
            ChatMessage(role=Role.ASSISTANT, content="earlier answer"),
        ),
        now="Friday 03 October 2026, 14:05",
    )

    contents = texts(asked[0])
    clock_at = next(i for i, c in enumerate(contents) if "It is now" in c)
    answer_at = next(i for i, c in enumerate(contents) if "earlier answer" in c)
    last = contents[-1]

    assert answer_at < clock_at, contents
    assert clock_at == len(contents) - 1, contents
    assert last.rstrip().endswith("hi"), last
    assert last.index("It is now") < last.index("hi"), last


async def test_an_unset_clock_leaves_no_trace(make_orchestrator: Any) -> None:
    """`now` is optional by design -- a deployment told no timezone claims no time -- so empty
    must mean absent rather than an empty sentence."""
    asked = await run(make_orchestrator, now="")

    assert not any("It is now" in c for c in texts(asked[0])), texts(asked[0])


async def test_the_skills_slot_is_not_in_the_frame(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """The second volatile slot, and the one that survives any date-only fix.

    The router's choice changes whenever routing lands differently, and it used to sit at priority
    60 in the frame -- in front of the whole conversation. So a turn that picked a different skill
    re-read the history exactly as the clock did, once a minute.
    """
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(make_orchestrator, text="/tdd how do I test this?")

    frame, _ = split_frame(asked[0])

    assert not any("Red, green, refactor." in c for c in frame), frame


async def test_the_skill_body_still_reaches_her(make_orchestrator: Any, write_skill: Any) -> None:
    """Moved, not dropped."""
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(make_orchestrator, text="/tdd how do I test this?")

    _, rest = split_frame(asked[0])

    assert any("Red, green, refactor." in c for c in rest), rest


async def test_the_problems_slot_is_not_in_the_frame(make_orchestrator: Any) -> None:
    """The third volatile slot, and the one that arrived by accident.

    `problems` is what the browser could not draw this turn: empty on a turn that rendered cleanly,
    populated on one that did not. It is per-turn by definition, so in the frame it sat ahead of the
    entire conversation and any turn carrying a broken diagram re-read all of it -- the clock's bug,
    one commit later, in a slot nothing was currently populating.
    """
    asked = await run(
        make_orchestrator,
        text="draw a chart",
        problems="- `gdp.mmd`: Lexical error on line 2",
    )

    frame, _ = split_frame(asked[0])

    assert not any("Lexical error" in c for c in frame), frame


async def test_the_problems_still_reach_her(make_orchestrator: Any) -> None:
    """Moved, not dropped -- the browser's report is the only way she learns it."""
    asked = await run(
        make_orchestrator,
        text="draw a chart",
        problems="- `gdp.mmd`: Lexical error on line 2",
    )

    _, rest = split_frame(asked[0])

    assert any("Lexical error" in c for c in rest), rest


async def test_an_unset_problems_slot_leaves_no_trace(make_orchestrator: Any) -> None:
    """A clean turn must not carry an empty section that the next turn's will invalidate."""
    asked = await run(make_orchestrator, text="hello")

    _, rest = split_frame(asked[0])

    assert not any("could not draw" in c for c in rest), rest


async def test_the_frame_is_identical_whatever_the_problems_say(make_orchestrator: Any) -> None:
    """A turn that could not draw and a turn that did are otherwise identical requests."""
    clean, _ = split_frame((await run(make_orchestrator, text="draw a chart"))[0])
    broken, _ = split_frame(
        (
            await run(
                make_orchestrator,
                text="draw a chart",
                problems="- `gdp.mmd`: Lexical error on line 2",
            )
        )[0]
    )

    assert clean, "the frame should not be empty"
    assert clean == broken, "a drawing failure changed the frame"


async def test_the_frame_is_identical_whatever_the_skills_and_the_clock_say(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """The whole claim in one assertion: turn to turn, the cacheable prefix does not move."""
    write_skill("tdd", body="Red, green, refactor.")

    plain, _ = split_frame((await run(make_orchestrator, text="hello"))[0])
    skilled, _ = split_frame((await run(make_orchestrator, text="/tdd go"))[0])
    later, _ = split_frame((await run(make_orchestrator, now="Friday 03 October 2026, 23:59"))[0])

    assert plain, "the frame should not be empty"
    assert plain == skilled, "selecting a skill changed the frame"
    assert plain == later, "the clock changed the frame"


async def test_the_turn_still_completes_with_the_clock_moved(make_orchestrator: Any) -> None:
    """The point of the change is the cache, so the turn has to keep working while doing it."""
    from hera_chats import TurnClosed
    from hera_providers import FakeProvider, text_turn

    turn = make_orchestrator(FakeProvider([text_turn("Still here.")])).begin(
        TurnContext(text="what time is it?", now="Friday 03 October 2026, 14:05")
    )

    events = await drain(turn.stream())

    assert isinstance(events[-1], TurnClosed)
    assert events[-1].reason == "completed"


async def test_roles_alternate_with_all_three_notes_present(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """Strict templates answer an *empty message* when roles do not alternate.

    Ministral and GPT-OSS in LM Studio both do, recorded in ``docs/prototype.md``. Moving the
    clock, the browser report and the skills after the history put three user messages in a row,
    so a supported target returned nothing at all. This is a correctness requirement, and it is
    the one thing in this file that was never asserted -- every other test here checks *where*
    something sits, not whether the shape a strict template rejects is the shape we produce.
    """
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(
        make_orchestrator,
        text="hi",
        now="Friday 03 October 2026, 14:05",
        problems="- `gdp.mmd`: Lexical error on line 2",
    )

    roles = [message.role for message in asked[0].messages]

    assert all(a is not b for a, b in pairwise(roles)), roles


async def test_the_notes_share_one_message_with_the_question_last(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """Merged, not dropped, and the question is still the final thing she reads."""
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(
        make_orchestrator,
        text="/tdd how do I test this?",
        now="Friday 03 October 2026, 14:05",
        problems="- `gdp.mmd`: Lexical error on line 2",
    )

    last = texts(asked[0])[-1]

    assert "It is now" in last, last
    assert "Lexical error" in last, last
    assert "Red, green, refactor." in last, last
    assert last.rstrip().endswith("how do I test this?"), last


async def test_the_skill_block_is_marked_as_instructions_not_as_speech(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """A skill used to be a system section. ADR 20 moved it after the history for the cache, and
    that cost it its standing: inside a user-role message it reads as something the person typed.

    A system message after the history is not an option -- the strict templates that answer an
    empty message on adjacent roles are the same ones that will not take one -- and ``developer``
    is not portable. So the boundary is stated in the text instead, and this pins it, because
    "they are instructions" is exactly the sort of thing a later edit drops for being redundant.
    """
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(make_orchestrator, text="/tdd how do I test this?")

    last = texts(asked[0])[-1]

    assert "skill instructions" in last, last
    assert "not something the person said" in last, last
    assert "Red, green, refactor." in last, last


async def test_no_skill_text_appears_in_a_system_or_developer_message(
    make_orchestrator: Any, write_skill: Any
) -> None:
    """The cost of the move, stated as a test so nobody re-adds the skills slot to the frame

    expecting only a cache win. If this ever passes, the frame is carrying the body again and the
    boundary text is duplicating instructions rather than replacing them.
    """
    write_skill("tdd", body="Red, green, refactor.")

    asked = await run(make_orchestrator, text="/tdd how do I test this?")

    authoritative = [
        str(m.content) for m in asked[0].messages if m.role.value in ("system", "developer")
    ]

    assert not any("Red, green, refactor." in c for c in authoritative), authoritative
