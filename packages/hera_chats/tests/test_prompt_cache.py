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
    """The exact position: conversation, then clock, then what she was asked.

    Between the history and the question rather than after both, because a note that follows the
    question reads as part of it.
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
    question_at = len(contents) - 1

    assert answer_at < clock_at < question_at, contents
    assert contents[question_at] == "hi", contents


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
